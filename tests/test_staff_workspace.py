from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import tempfile
import hashlib
import json
import unittest
from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch

from code import analytics_reports, auth, conversation, dialogue, handoff, knowledge, logger, staff_content
from ui import staff_workspace


class StaffWorkspaceStorageTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def _create_for_student(
        self,
        student_id: str,
        student_name: str | None = None,
        session_id: str | None = None,
    ) -> dict:
        with (
            patch.object(auth, "is_student", return_value=True),
            patch.object(auth, "get_current_user_id", return_value=student_id),
        ):
            return conversation.create_conversation(
                student_id,
                student_name,
                session_id=session_id,
            )

    def test_staff_account_cannot_be_self_registered(self) -> None:
        with (
            patch.object(auth, "DATA_DIR", self.root),
            patch.object(auth, "USERS_FILE", self.root / "users.json"),
        ):
            created, message = auth.create_account("new-staff", "password", role="staff")
            self.assertFalse(created)
            self.assertIn("authorized administrator", message)
            self.assertFalse((self.root / "users.json").exists())

    def test_student_self_registration_uses_existing_store_and_secure_hash(self) -> None:
        users_file = self.root / "users.json"
        with (
            patch.object(auth, "DATA_DIR", self.root),
            patch.object(auth, "USERS_FILE", users_file),
        ):
            created, _ = auth.create_account("student-1", "password", "Student One")
            self.assertTrue(created)
            student = auth._load_users()["student-1"]
            self.assertEqual(student["role"], "student")
            self.assertTrue(student["password_hash"].startswith("pbkdf2_sha256$"))

    def test_render_account_storage_requires_database_url(self) -> None:
        with (
            patch.dict("os.environ", {"RENDER_SERVICE_ID": "render-service"}, clear=True),
            patch.object(auth, "_deployment_setting", return_value=""),
        ):
            with self.assertRaisesRegex(auth.AccountStoreError, "Set DATABASE_URL"):
                auth._load_users()

    def test_postgres_account_store_loads_and_saves_users(self) -> None:
        user_record = {"name": "Student One", "role": "student"}
        connection = MagicMock()
        cursor = MagicMock()
        connection.__enter__.return_value = connection
        connection.cursor.return_value.__enter__.return_value = cursor
        cursor.fetchall.return_value = [("student-1", user_record)]

        with (
            patch.dict(
                "os.environ",
                {"DATABASE_URL": "postgresql://test.invalid/db"},
                clear=True,
            ),
            patch.object(
                auth,
                "_deployment_setting",
                side_effect=lambda key: os.environ.get(key, ""),
            ),
            patch.object(
                auth,
                "_connect_to_database",
                return_value=connection,
            ) as connect_mock,
        ):
            users = auth._load_users()
            self.assertEqual(users, {"student-1": user_record})

            auth._save_users(users)

        self.assertEqual(connect_mock.call_count, 2)
        connect_mock.assert_called_with("postgresql://test.invalid/db")
        cursor.executemany.assert_called_once()

    def test_postgres_connections_require_ssl(self) -> None:
        with patch.object(auth.psycopg, "connect") as connect_mock:
            auth._connect_to_database("postgresql://test.invalid/db")

        connect_mock.assert_called_once_with(
            "postgresql://test.invalid/db",
            sslmode="require",
        )

    def test_existing_json_accounts_can_be_migrated_to_postgres(self) -> None:
        users_file = self.root / "users.json"
        legacy_users = {
            "student-1": {
                "password_hash": "existing-hash",
                "name": "Student One",
                "role": "student",
            }
        }
        users_file.write_text(
            json.dumps(legacy_users),
            encoding="utf-8",
        )
        connection = MagicMock()
        cursor = MagicMock()
        connection.__enter__.return_value = connection
        connection.cursor.return_value.__enter__.return_value = cursor
        cursor.fetchall.return_value = []

        with (
            patch.object(auth, "USERS_FILE", users_file),
            patch.dict(
                "os.environ",
                {"MIGRATE_USERS_JSON_TO_DATABASE": "true"},
            ),
            patch.object(
                auth,
                "_connect_to_database",
                return_value=connection,
            ),
        ):
            migrated = auth._load_postgres_users(
                "postgresql://test.invalid/db"
            )

        self.assertEqual(migrated, legacy_users)
        cursor.executemany.assert_called_once()

    def test_staff_login_ignores_id_letter_case(self) -> None:
        users_file = self.root / "users.json"
        session_state = {}
        with (
            patch.object(auth, "DATA_DIR", self.root),
            patch.object(auth, "USERS_FILE", users_file),
        ):
            auth._save_users({
                "Earl_Staff": {
                    "password_hash": hashlib.sha256(b"legacy-pass").hexdigest(),
                    "name": "Earl Staff",
                    "role": "staff",
                }
            })
            with patch.object(auth.st, "session_state", session_state):
                success, message = auth.login(
                    "Earl_staff", "legacy-pass", expected_role="staff"
                )
            self.assertTrue(success, message)
            self.assertEqual(session_state[auth.SESSION_KEY], "Earl_Staff")
            self.assertEqual(session_state[auth.SESSION_ROLE_KEY], "staff")

    def test_signed_browser_session_restores_login_and_password_change_revokes_it(self) -> None:
        users_file = self.root / "users.json"
        session_state = {}
        with (
            patch.object(auth, "DATA_DIR", self.root),
            patch.object(auth, "USERS_FILE", users_file),
            patch.object(auth.st, "session_state", session_state),
        ):
            auth._save_users({
                "student-1": {
                    "password_hash": auth._hash_password("student-password"),
                    "name": "Student One",
                    "role": "student",
                }
            })
            success, message = auth.login(
                "student-1",
                "student-password",
                expected_role="student",
            )
            self.assertTrue(success, message)
            token = auth.create_session_token()

            session_state.clear()
            self.assertTrue(auth.restore_session_token(token))
            self.assertEqual(session_state[auth.SESSION_KEY], "student-1")
            self.assertEqual(session_state[auth.SESSION_ROLE_KEY], "student")

            session_state.clear()
            encoded_payload, signature = token.rsplit(".", 1)
            tampered_signature = ("0" if signature[0] != "0" else "1") + signature[1:]
            self.assertFalse(
                auth.restore_session_token(f"{encoded_payload}.{tampered_signature}")
            )

            users = auth._load_users()
            users["student-1"]["password_hash"] = auth._hash_password("new-password")
            auth._save_users(users)
            self.assertFalse(auth.restore_session_token(token))

    def test_signed_browser_session_expires(self) -> None:
        users_file = self.root / "users.json"
        session_state = {
            auth.SESSION_KEY: "student-1",
            auth.SESSION_ROLE_KEY: "student",
        }
        with (
            patch.object(auth, "DATA_DIR", self.root),
            patch.object(auth, "USERS_FILE", users_file),
            patch.object(auth.st, "session_state", session_state),
        ):
            auth._save_users({
                "student-1": {
                    "password_hash": auth._hash_password("student-password"),
                    "role": "student",
                }
            })
            with patch.object(auth.time, "time", return_value=1_000):
                token = auth.create_session_token()
            with patch.object(
                auth.time,
                "time",
                return_value=1_000 + auth.SESSION_COOKIE_TTL_SECONDS + 1,
            ):
                self.assertFalse(auth.restore_session_token(token))

    def test_bootstrap_admin_is_created_from_deployment_secrets_and_can_manage_staff(self) -> None:
        users_file = self.root / "users.json"
        session_state = {}
        bootstrap_settings = {
            "BOOTSTRAP_ADMIN_ID": "first-admin",
            "BOOTSTRAP_ADMIN_PASSWORD": "initial-admin-password",
            "BOOTSTRAP_ADMIN_NAME": "First Administrator",
            "BOOTSTRAP_ADMIN_EMAIL": "admin@gra.edu",
            "BOOTSTRAP_ADMIN_DEPARTMENT": "Administration",
        }
        with (
            patch.object(auth, "DATA_DIR", self.root),
            patch.object(auth, "USERS_FILE", users_file),
            patch.object(auth, "ADMIN_ENV_PATH", self.root / "absent.env"),
            patch.dict("os.environ", bootstrap_settings, clear=True),
            patch.object(
                auth,
                "_deployment_setting",
                side_effect=lambda key: bootstrap_settings.get(key, ""),
            ),
            patch.object(auth.st, "secrets", {}),
            patch.object(auth.st, "session_state", session_state),
        ):
            success, message = auth.login(
                "FIRST-ADMIN",
                "initial-admin-password",
                expected_role="staff",
            )
            self.assertTrue(success, message)
            self.assertTrue(auth.is_admin())
            created, message = auth.create_staff_account(
                "new-staff",
                "New Staff",
                "new.staff@gra.edu",
                "Registrar",
                "staff-password",
                "staff-password",
            )
            self.assertTrue(created, message)
            users = auth._load_users()

            self.assertEqual(users["first-admin"]["role"], "staff")
            self.assertEqual(users["first-admin"]["email"], "admin@gra.edu")
            self.assertEqual(users["new-staff"]["role"], "staff")
            self.assertTrue(
                auth._verify_password(
                    "initial-admin-password",
                    users["first-admin"]["password_hash"],
                )
            )

    def test_admin_creates_staff_account_and_prevents_duplicate_ids_and_emails(self) -> None:
        users_file = self.root / "users.json"
        with (
            patch.object(auth, "DATA_DIR", self.root),
            patch.object(auth, "USERS_FILE", users_file),
            patch.dict("os.environ", {"STAFF_ADMIN_IDS": "admin-1"}),
            patch.object(auth, "is_staff", return_value=True),
            patch.object(auth, "get_current_user_id", return_value="ADMIN-1"),
        ):
            original_student_hash = auth._hash_password("student-pass")
            auth._save_users({
                "student-1": {
                    "password_hash": original_student_hash,
                    "name": "Student One",
                    "role": "student",
                }
            })
            created, _ = auth.create_staff_account(
                "staff-1",
                "Staff One",
                "STAFF.ONE@GRA.EDU",
                "Registrar",
                "secure-password",
                "secure-password",
            )
            users = auth._load_users()

            self.assertTrue(created)
            self.assertEqual(users["student-1"]["role"], "student")
            self.assertEqual(users["student-1"]["password_hash"], original_student_hash)
            self.assertEqual(users["staff-1"]["role"], "staff")
            self.assertEqual(users["staff-1"]["email"], "staff.one@gra.edu")
            self.assertEqual(users["staff-1"]["department"], "Registrar")
            self.assertTrue(
                users["staff-1"]["password_hash"].startswith("pbkdf2_sha256$")
            )
            duplicate_id, _ = auth.create_staff_account(
                "STAFF-1",
                "Another Staff",
                "another@gra.edu",
                "Registrar",
                "secure-password",
                "secure-password",
            )
            duplicate_email, _ = auth.create_staff_account(
                "staff-2",
                "Another Staff",
                "Staff.One@gra.edu",
                "Registrar",
                "secure-password",
                "secure-password",
            )
            self.assertFalse(duplicate_id)
            self.assertFalse(duplicate_email)

    def test_created_staff_account_authenticates_with_staff_role(self) -> None:
        users_file = self.root / "users.json"
        session_state = {}
        with (
            patch.object(auth, "DATA_DIR", self.root),
            patch.object(auth, "USERS_FILE", users_file),
            patch.dict("os.environ", {"STAFF_ADMIN_IDS": "admin-1"}),
            patch.object(auth, "is_staff", return_value=True),
            patch.object(auth, "get_current_user_id", return_value="admin-1"),
        ):
            auth.create_staff_account(
                "new-staff",
                "New Staff",
                "new.staff@gra.edu",
                "Registrar",
                "secure-password",
                "secure-password",
            )
            with patch.object(auth.st, "session_state", session_state):
                success, message = auth.login(
                    "new-staff", "secure-password", expected_role="staff"
                )

            self.assertTrue(success, message)
            self.assertEqual(session_state[auth.SESSION_KEY], "new-staff")
            self.assertEqual(session_state[auth.SESSION_ROLE_KEY], "staff")
            self.assertTrue(auth._verify_password(
                "secure-password",
                auth._load_users()["new-staff"]["password_hash"],
            ))

    def test_ordinary_staff_and_student_cannot_create_staff_accounts(self) -> None:
        with (
            patch.object(auth, "DATA_DIR", self.root),
            patch.object(auth, "USERS_FILE", self.root / "users.json"),
            patch.dict("os.environ", {"STAFF_ADMIN_IDS": "admin-1"}),
        ):
            for role, user_id in (("staff", "staff-1"), ("student", "student-1")):
                with (
                    patch.object(auth, "is_staff", return_value=role == "staff"),
                    patch.object(auth, "get_current_user_id", return_value=user_id),
                ):
                    created, _ = auth.create_staff_account(
                        "new-staff",
                        "New Staff",
                        "new@gra.edu",
                        "Registrar",
                        "secure-password",
                        "secure-password",
                    )
                    self.assertFalse(created)
            self.assertFalse((self.root / "users.json").exists())

    def test_staff_admin_allowlist_can_be_configured_from_dotenv(self) -> None:
        env_file = self.root / ".env"
        env_file.write_text("STAFF_ADMIN_IDS=admin-1,admin-2\n", encoding="utf-8")
        with (
            patch.object(auth, "ADMIN_ENV_PATH", env_file),
            patch.dict("os.environ", {"STAFF_ADMIN_IDS": ""}),
            patch.object(auth, "is_staff", return_value=True),
            patch.object(auth, "get_current_user_id", return_value="ADMIN-2"),
        ):
            self.assertTrue(auth.is_admin())

    def test_staff_creation_validates_fields_and_preserves_corrupt_database(self) -> None:
        users_file = self.root / "users.json"
        with (
            patch.object(auth, "DATA_DIR", self.root),
            patch.object(auth, "USERS_FILE", users_file),
            patch.dict("os.environ", {"STAFF_ADMIN_IDS": "admin-1"}),
            patch.object(auth, "is_staff", return_value=True),
            patch.object(auth, "get_current_user_id", return_value="admin-1"),
        ):
            invalid, message = auth.create_staff_account(
                "staff-1", "New Staff", "not-an-email", "Registrar",
                "secure-password", "secure-password",
            )
            self.assertFalse(invalid)
            self.assertIn("Official Email", message)

            users_file.write_text("{invalid json", encoding="utf-8")
            failed, message = auth.create_staff_account(
                "staff-1", "New Staff", "new@gra.edu", "Registrar",
                "secure-password", "secure-password",
            )
            self.assertFalse(failed)
            self.assertIn("account database", message)
            self.assertEqual(users_file.read_text(encoding="utf-8"), "{invalid json")

    def test_staff_creation_rejects_mismatched_passwords(self) -> None:
        with (
            patch.dict("os.environ", {"STAFF_ADMIN_IDS": "admin-1"}),
            patch.object(auth, "is_staff", return_value=True),
            patch.object(auth, "get_current_user_id", return_value="admin-1"),
        ):
            created, message = auth.create_staff_account(
                "staff-1", "New Staff", "new@gra.edu", "Registrar",
                "secure-password", "different-password",
            )
            self.assertFalse(created)
            self.assertIn("do not match", message)

    def test_legacy_student_password_still_verifies(self) -> None:
        legacy_hash = hashlib.sha256(b"legacy-pass").hexdigest()
        self.assertTrue(auth._verify_password("legacy-pass", legacy_hash))
        self.assertFalse(auth._verify_password("wrong-pass", legacy_hash))

    def test_approved_articles_are_searchable_but_drafts_are_not(self) -> None:
        articles_path = self.root / "articles.json"
        with patch.object(staff_content, "ARTICLES_PATH", articles_path):
            article = staff_content.save_article(
                "Quantum Zebra Registrar Notice",
                "Official details about the quantum zebra registrar notice.",
                "Other",
                "Verified circular QZ-1",
                "staff-1",
            )
            draft_hits = knowledge.search("Quantum Zebra Registrar Notice")
            self.assertFalse(
                any(hit["section"] == "staff-verified articles" for hit in draft_hits)
            )
            staff_content.set_article_status(article["id"], "approved", "staff-1")
            approved_hits = knowledge.search("Quantum Zebra Registrar Notice")
            self.assertTrue(
                any(hit["section"] == "staff-verified articles" for hit in approved_hits)
            )

    def test_resolved_conversation_is_retained_for_staff_history(self) -> None:
        conversations_dir = self.root / "conversations"
        with patch.object(conversation, "CONV_DIR", conversations_dir):
            created = self._create_for_student("student-1", "Student")
            with (
                patch.object(auth, "is_staff", return_value=True),
                patch.object(auth, "get_current_user_id", return_value="staff-1"),
            ):
                resolved = conversation.update_conversation_status(
                    created["session_id"], "closed", "staff-1"
                )
            self.assertIsNotNone(resolved)
            self.assertEqual(conversation.get_closed_conversations()[0]["status"], "closed")

    def test_staff_request_gets_ai_fallback_after_timeout(self) -> None:
        conversations_dir = self.root / "conversations"
        with patch.object(conversation, "CONV_DIR", conversations_dir):
            created = self._create_for_student("student-1", "Student")
            with (
                patch.object(auth, "is_student", return_value=True),
                patch.object(auth, "get_current_user_id", return_value="student-1"),
            ):
                conversation.add_message(
                    created["session_id"],
                    "student",
                    "What are the enrollment requirements?",
                    sender_id="student-1",
                )
                waiting = conversation.update_conversation_status(
                    created["session_id"], "waiting"
                )
                self.assertIsNotNone(waiting)
                waiting_since = waiting["waiting_since"]
                old_wait = (
                    datetime.now() - timedelta(seconds=conversation.STAFF_RESPONSE_TIMEOUT_SECONDS + 1)
                ).isoformat(timespec="microseconds")
                waiting["waiting_since"] = old_wait
                conversation._save_conversation(waiting)
                self.assertEqual(
                    conversation.staff_response_seconds_remaining(waiting),
                    0,
                )
                fallback = conversation.add_staff_timeout_reply(
                    created["session_id"],
                    old_wait,
                    "Here are the enrollment requirements.",
                    {"staff_timeout_fallback": True},
                )

            self.assertIsNotNone(fallback)
            self.assertEqual(fallback["role"], "assistant")
            updated = conversation.get_conversation(created["session_id"])
            self.assertEqual(updated["status"], "active")
            self.assertNotIn("waiting_since", updated)
            self.assertEqual(updated["messages"][-1]["text"], "Here are the enrollment requirements.")

    def test_staff_reply_cancels_pending_ai_fallback(self) -> None:
        conversations_dir = self.root / "conversations"
        with patch.object(conversation, "CONV_DIR", conversations_dir):
            created = self._create_for_student("student-1", "Student")
            with (
                patch.object(auth, "is_student", return_value=True),
                patch.object(auth, "get_current_user_id", return_value="student-1"),
            ):
                waiting = conversation.update_conversation_status(
                    created["session_id"], "waiting"
                )
            waiting_since = waiting["waiting_since"]
            with (
                patch.object(auth, "is_staff", return_value=True),
                patch.object(auth, "get_current_user_id", return_value="staff-1"),
            ):
                conversation.assign_staff_to_conversation(
                    created["session_id"], "staff-1", "Staff One"
                )
                conversation.add_message(
                    created["session_id"],
                    "staff",
                    "I can help with that.",
                    sender_id="staff-1",
                )
            with (
                patch.object(auth, "is_student", return_value=True),
                patch.object(auth, "get_current_user_id", return_value="student-1"),
            ):
                fallback = conversation.add_staff_timeout_reply(
                    created["session_id"],
                    waiting_since,
                    "AI fallback",
                )
            self.assertIsNone(fallback)
            updated = conversation.get_conversation(created["session_id"])
            self.assertEqual(updated["messages"][-1]["role"], "staff")
            self.assertNotIn("waiting_since", updated)
            self.assertTrue((conversations_dir / f"{created['session_id']}.json").exists())

    def test_conversation_creation_requires_student_owner_and_accepts_session_id(self) -> None:
        conversations_dir = self.root / "conversations"
        with patch.object(conversation, "CONV_DIR", conversations_dir):
            with patch.object(auth, "is_student", return_value=False):
                with self.assertRaises(PermissionError):
                    conversation.create_conversation("student-1", "Student")

            session_id = "123456abcdef"
            created = self._create_for_student(
                "student-1", "Student", session_id=session_id
            )
            self.assertEqual(created["session_id"], session_id)
            self.assertTrue((conversations_dir / f"{session_id}.json").exists())
            with self.assertRaises(ValueError):
                self._create_for_student(
                    "student-1", "Student", session_id=session_id
                )

    def test_student_can_request_staff_after_ai_cannot_answer(self) -> None:
        conversations_dir = self.root / "conversations"
        with patch.object(conversation, "CONV_DIR", conversations_dir):
            created = self._create_for_student("student-1", "Student One")
            with (
                patch.object(auth, "is_student", return_value=True),
                patch.object(auth, "get_current_user_id", return_value="student-1"),
            ):
                waiting = conversation.update_conversation_status(
                    created["session_id"], "waiting"
                )
                confirmation = conversation.add_message(
                    created["session_id"],
                    "assistant",
                    "Your request has been sent to staff.",
                    meta={"intent": "staff_requested"},
                )
                with self.assertRaises(PermissionError):
                    conversation.update_conversation_status(
                        created["session_id"], "active"
                    )

            self.assertEqual(waiting["status"], "waiting")
            self.assertEqual(confirmation["meta"]["intent"], "staff_requested")
            self.assertEqual(
                conversation.get_conversation(created["session_id"])["status"],
                "waiting",
            )

    def test_handoff_service_queues_student_request_and_notice(self) -> None:
        conversations_dir = self.root / "conversations"
        with patch.object(conversation, "CONV_DIR", conversations_dir):
            created = self._create_for_student("student-1", "Student One")
            with (
                patch.object(auth, "is_student", return_value=True),
                patch.object(auth, "get_current_user_id", return_value="student-1"),
            ):
                updated, notice = handoff.request_staff_response(
                    created["session_id"]
                )
            self.assertEqual(updated["status"], "waiting")
            self.assertTrue(updated["waiting_since"])
            self.assertEqual(notice["meta"]["intent"], "staff_requested")
            self.assertEqual(
                conversation.get_conversation(created["session_id"])["messages"][-1]["text"],
                notice["text"],
            )

    def test_handoff_service_generates_fallback_only_for_own_expired_request(self) -> None:
        conversations_dir = self.root / "conversations"
        with patch.object(conversation, "CONV_DIR", conversations_dir):
            created = self._create_for_student("student-1", "Student One")
            with (
                patch.object(auth, "is_student", return_value=True),
                patch.object(auth, "get_current_user_id", return_value="student-1"),
            ):
                conversation.add_message(
                    created["session_id"],
                    "student",
                    "How can I enroll?",
                    sender_id="student-1",
                )
                waiting = conversation.update_conversation_status(
                    created["session_id"], "waiting"
                )
                waiting["waiting_since"] = (
                    datetime.now()
                    - timedelta(seconds=conversation.STAFF_RESPONSE_TIMEOUT_SECONDS + 1)
                ).isoformat(timespec="microseconds")
                conversation._save_conversation(waiting)
                policy = dialogue.Policy()
                with patch.object(
                    dialogue,
                    "handle",
                    return_value=dialogue.Reply(
                        text="Here are the enrollment steps.",
                        intent="ask_requirements",
                        confidence=0.8,
                        source="school knowledge",
                    ),
                ) as handle:
                    fallback = handoff.generate_timeout_fallback(
                        created["session_id"], "student-1", policy
                    )

                self.assertIsNotNone(fallback)
                self.assertEqual(fallback["meta"]["source"], "AI fallback after staff response timeout")
                self.assertEqual(fallback["text"], "Here are the enrollment steps.")
                handle.assert_called_once()
                with self.assertRaises(PermissionError):
                    handoff.generate_timeout_fallback(
                        created["session_id"], "student-2", policy
                    )

    def test_follow_up_to_assigned_staff_starts_fresh_response_timeout(self) -> None:
        conversations_dir = self.root / "conversations"
        with patch.object(conversation, "CONV_DIR", conversations_dir):
            created = self._create_for_student("student-1", "Student One")
            with (
                patch.object(auth, "is_staff", return_value=True),
                patch.object(auth, "get_current_user_id", return_value="staff-1"),
            ):
                assigned = conversation.assign_staff_to_conversation(
                    created["session_id"], "staff-1", "Staff One"
                )
            self.assertIsNotNone(assigned)
            self.assertNotIn("waiting_since", assigned)

            with (
                patch.object(auth, "is_student", return_value=True),
                patch.object(auth, "get_current_user_id", return_value="student-1"),
            ):
                message = conversation.add_message(
                    created["session_id"],
                    "student",
                    "I have one more question.",
                    sender_id="student-1",
                )

            updated = conversation.get_conversation(created["session_id"])
            self.assertEqual(message["text"], "I have one more question.")
            self.assertEqual(updated["status"], "waiting")
            self.assertTrue(updated.get("waiting_since"))
            remaining = conversation.staff_response_seconds_remaining(updated)
            self.assertIsNotNone(remaining)
            self.assertGreaterEqual(remaining, 0)
            self.assertLessEqual(remaining, conversation.STAFF_RESPONSE_TIMEOUT_SECONDS)

    def test_staff_cannot_take_over_an_inquiry_owned_by_online_staff(self) -> None:
        conversations_dir = self.root / "conversations"
        with patch.object(conversation, "CONV_DIR", conversations_dir):
            created = self._create_for_student("student-1", "Student One")
            with (
                patch.object(auth, "is_staff", return_value=True),
                patch.object(auth, "get_current_user_id", return_value="staff-1"),
            ):
                assigned = conversation.assign_staff_to_conversation(
                    created["session_id"], "staff-1", "Staff One"
                )
            self.assertIsNotNone(assigned)
            with (
                patch.object(auth, "is_staff", return_value=True),
                patch.object(auth, "get_current_user_id", return_value="staff-2"),
                patch.object(conversation.staff_presence, "is_staff_online", return_value=True),
            ):
                takeover = conversation.assign_staff_to_conversation(
                    created["session_id"], "staff-2", "Staff Two"
                )
            self.assertIsNone(takeover)
            self.assertEqual(
                conversation.get_conversation(created["session_id"])["assigned_staff"],
                "staff-1",
            )

    def test_messages_enforce_owner_role_resolution_and_order(self) -> None:
        conversations_dir = self.root / "conversations"
        with patch.object(conversation, "CONV_DIR", conversations_dir):
            created = self._create_for_student("student-1", "Student One")
            session_id = created["session_id"]

            with (
                patch.object(auth, "is_student", return_value=True),
                patch.object(auth, "get_current_user_id", return_value="student-2"),
            ):
                with self.assertRaises(PermissionError):
                    conversation.add_message(session_id, "student", "Not my chat")

            with (
                patch.object(auth, "is_student", return_value=True),
                patch.object(auth, "get_current_user_id", return_value="student-1"),
            ):
                with self.assertRaises(PermissionError):
                    conversation.add_message(
                        session_id, "student", "Spoofed sender", sender_id="student-2"
                    )
                student_message = conversation.add_message(
                    session_id, "student", "Where can I pay?", sender_id="student-1"
                )
                assistant_message = conversation.add_message(
                    session_id, "assistant", "Please visit the cashier."
                )

            with (
                patch.object(auth, "is_staff", return_value=True),
                patch.object(auth, "get_current_user_id", return_value="staff-1"),
            ):
                with self.assertRaisesRegex(PermissionError, "Take over"):
                    conversation.add_message(
                        session_id,
                        "staff",
                        "The cashier is open until 4 PM.",
                        sender_id="staff-1",
                    )
                assigned = conversation.assign_staff_to_conversation(
                    session_id, "staff-1", "Staff One"
                )
                self.assertIsNotNone(assigned)
                staff_message = conversation.add_message(
                    session_id,
                    "staff",
                    "The cashier is open until 4 PM.",
                    sender_id="staff-1",
                )
                conversation.update_conversation_status(session_id, "closed")

            self.assertEqual(
                [student_message["role"], assistant_message["role"], staff_message["role"]],
                ["student", "assistant", "staff"],
            )
            self.assertEqual(
                [message["role"] for message in conversation.get_conversation(session_id)["messages"]],
                ["student", "assistant", "staff"],
            )
            self.assertLess(student_message["timestamp"], assistant_message["timestamp"])
            self.assertLess(assistant_message["timestamp"], staff_message["timestamp"])
            with (
                patch.object(auth, "is_student", return_value=True),
                patch.object(auth, "get_current_user_id", return_value="student-1"),
            ):
                with self.assertRaises(ValueError):
                    conversation.add_message(session_id, "student", "Reply after resolution")

    def test_dialogue_log_uses_the_conversation_session_id(self) -> None:
        conversations_dir = self.root / "conversations"
        log_path = self.root / "chat_log.jsonl"
        session_id = "abcdef123456"
        with (
            patch.object(conversation, "CONV_DIR", conversations_dir),
            patch.object(logger, "LOG_PATH", log_path),
        ):
            created = self._create_for_student(
                "student-1", "Student One", session_id=session_id
            )
            session = dialogue.Session(session_id=created["session_id"])
            reply = dialogue.Reply(
                text="Payment details",
                intent="ask_fees_payment",
                confidence=0.9,
                source="test",
            )
            dialogue._log("Where can I pay?", reply, session, "student-1", "Student One")

            self.assertEqual(logger.read_logs()[0]["session_id"], created["session_id"])

    def test_question_review_includes_live_student_messages_and_deduplicates_logs(self) -> None:
        logs = [
            {
                "session_id": "session-1",
                "text": "What are the requirements?",
                "ts": "2026-11-02T10:00:01",
                "intent": "ask_requirements",
                "confidence": 0.9,
                "answered": True,
            },
            {
                "session_id": "old-session",
                "text": "Unknown question",
                "ts": "2026-11-02T09:00:00",
                "intent": "unknown",
                "confidence": 0.2,
                "answered": False,
            },
            {
                "event": "feedback",
                "session_id": "session-1",
                "text": "Thanks",
                "answered": True,
            },
        ]
        conversations = [
            {
                "session_id": "session-1",
                "student_id": "student-1",
                "student_name": "Student One",
                "status": "waiting",
                "messages": [
                    {
                        "id": "message-1",
                        "role": "student",
                        "text": "What are the requirements?",
                        "timestamp": "2026-11-02T10:00:00",
                    },
                    {
                        "id": "message-2",
                        "role": "assistant",
                        "text": "Here are the requirements.",
                        "meta": {
                            "intent": "ask_requirements",
                            "confidence": 0.9,
                            "answered": True,
                        },
                    },
                    {
                        "id": "message-3",
                        "role": "student",
                        "text": "Please connect me to staff.",
                        "timestamp": "2026-11-02T10:01:00",
                    },
                    {
                        "id": "message-4",
                        "role": "assistant",
                        "text": "Your message is saved in the staff queue.",
                        "meta": {
                            "intent": "staff_notified",
                            "source": "conversation - staff routing",
                        },
                    },
                    {
                        "id": "message-5",
                        "role": "student",
                        "text": "Voice recording",
                        "timestamp": "2026-11-02T10:02:00",
                        "meta": {"intent": "voice_recording"},
                    },
                ],
            }
        ]

        rows = staff_workspace._question_review_rows(logs, conversations)

        self.assertEqual(
            [row["text"] for row in rows],
            [
                "Please connect me to staff.",
                "What are the requirements?",
                "Unknown question",
            ],
        )
        self.assertEqual(rows[0]["status"], "Sent to staff")
        self.assertEqual(rows[0]["intent"], "Staff hand-off")
        self.assertEqual(rows[1]["status"], "AI answered")
        self.assertEqual(rows[2]["status"], "Unanswered")

    def test_student_recent_conversations_are_isolated_by_student_id(self) -> None:
        conversations_dir = self.root / "conversations"
        with patch.object(conversation, "CONV_DIR", conversations_dir):
            owned = self._create_for_student("student-1", "Student One")
            self._create_for_student("student-2", "Student Two")
            resolved = self._create_for_student("student-1", "Student One")
            waiting = self._create_for_student("student-1", "Student One")
            with (
                patch.object(auth, "is_staff", return_value=True),
                patch.object(auth, "get_current_user_id", return_value="staff-1"),
            ):
                conversation.update_conversation_status(resolved["session_id"], "closed")
                conversation.update_conversation_status(waiting["session_id"], "waiting")

            recent = conversation.get_student_conversations("student-1")

            self.assertEqual(
                {item["session_id"] for item in recent},
                {owned["session_id"], resolved["session_id"], waiting["session_id"]},
            )
            self.assertNotIn(
                "student-2",
                {item.get("student_id") for item in recent},
            )
            self.assertEqual(
                conversation.get_student_conversation("student-1")["status"],
                "waiting",
            )

    def test_staff_can_permanently_delete_one_conversation_and_its_log_rows(self) -> None:
        conversations_dir = self.root / "conversations"
        log_path = self.root / "chat_log.jsonl"
        with (
            patch.object(conversation, "CONV_DIR", conversations_dir),
            patch.object(logger, "LOG_PATH", log_path),
            patch.object(auth, "is_staff", return_value=True),
        ):
            target = self._create_for_student("student-1", "Student One")
            retained = self._create_for_student("student-2", "Student Two")
            logger.log_turn({
                "session_id": target["session_id"],
                "student_id": "student-1",
                "text": "Remove this inquiry",
            })
            logger.log_turn({
                "session_id": retained["session_id"],
                "student_id": "student-2",
                "text": "Keep this inquiry",
            })

            self.assertTrue(conversation.delete_conversation(target["session_id"]))
            self.assertIsNone(conversation.get_conversation(target["session_id"]))
            self.assertIsNotNone(conversation.get_conversation(retained["session_id"]))
            remaining_logs = logger.read_logs()
            self.assertEqual(len(remaining_logs), 1)
            self.assertEqual(remaining_logs[0]["session_id"], retained["session_id"])

    def test_only_staff_can_permanently_delete_conversations(self) -> None:
        conversations_dir = self.root / "conversations"
        with (
            patch.object(conversation, "CONV_DIR", conversations_dir),
            patch.object(auth, "is_staff", return_value=False),
        ):
            created = self._create_for_student("student-1", "Student")
            with self.assertRaises(PermissionError):
                conversation.delete_conversation(created["session_id"])
            self.assertIsNotNone(conversation.get_conversation(created["session_id"]))

    def test_student_can_permanently_delete_only_their_own_conversation(self) -> None:
        conversations_dir = self.root / "conversations"
        log_path = self.root / "chat_log.jsonl"
        with (
            patch.object(conversation, "CONV_DIR", conversations_dir),
            patch.object(logger, "LOG_PATH", log_path),
            patch.object(auth, "is_student", return_value=True),
            patch.object(auth, "get_current_user_id", return_value="student-1"),
        ):
            own = self._create_for_student("student-1", "Student One")
            other = self._create_for_student("student-2", "Student Two")
            logger.log_turn({
                "session_id": own["session_id"],
                "student_id": "student-1",
                "text": "My question",
            })
            logger.log_turn({
                "session_id": other["session_id"],
                "student_id": "student-2",
                "text": "Other student's question",
            })

            self.assertTrue(conversation.delete_own_conversation(own["session_id"]))
            self.assertIsNone(conversation.get_conversation(own["session_id"]))
            self.assertIsNotNone(conversation.get_conversation(other["session_id"]))
            self.assertEqual(
                [row["session_id"] for row in logger.read_logs()],
                [other["session_id"]],
            )
            with self.assertRaises(PermissionError):
                conversation.delete_own_conversation(other["session_id"])

    def test_staff_cannot_use_student_owned_conversation_delete(self) -> None:
        conversations_dir = self.root / "conversations"
        with (
            patch.object(conversation, "CONV_DIR", conversations_dir),
            patch.object(auth, "is_student", return_value=False),
        ):
            created = self._create_for_student("student-1", "Student")
            with self.assertRaises(PermissionError):
                conversation.delete_own_conversation(created["session_id"])
            self.assertIsNotNone(conversation.get_conversation(created["session_id"]))

    def test_document_upload_and_replacement_use_generated_storage_names(self) -> None:
        document_dir = self.root / "documents"
        with (
            patch.object(staff_content, "DATA_DIR", self.root),
            patch.object(staff_content, "DOCUMENTS_PATH", self.root / "documents.json"),
            patch.object(staff_content, "DOCUMENT_DIR", document_dir),
        ):
            created = staff_content.save_document(
                "..\\registrar.txt",
                b"first version",
                "Registrar",
                "staff-1",
                ["student-1"],
            )
            replaced = staff_content.replace_document(
                created["id"],
                "updated.txt",
                b"updated version",
                "Registrar",
                "staff-1",
                ["student-2"],
            )
            record, content = staff_content.read_document(replaced["id"])
            self.assertEqual(record["filename"], "updated.txt")
            self.assertEqual(content, b"updated version")
            self.assertRegex(record["stored_name"], r"^[a-f0-9]{32}\.txt$")
            self.assertEqual(record["shared_with"], ["student-2"])
            self.assertEqual(staff_content.documents_for_student("STUDENT-2"), [record])
            self.assertEqual(staff_content.documents_for_student("student-1"), [])
            with (
                patch.object(auth, "is_student", return_value=True),
                patch.object(auth, "get_current_user_id", return_value="student-2"),
            ):
                with self.assertRaises(PermissionError):
                    staff_content.read_document_for_student(record["id"], "student-1")
                student_record, student_content = staff_content.read_document_for_student(
                    record["id"], "student-2"
                )
            with (
                patch.object(auth, "is_student", return_value=True),
                patch.object(auth, "get_current_user_id", return_value="student-1"),
                self.assertRaises(PermissionError),
            ):
                staff_content.read_document_for_student(record["id"], "student-1")
            self.assertEqual(student_record["id"], record["id"])
            self.assertEqual(student_content, b"updated version")

    def test_document_upload_size_validation_distinguishes_empty_from_too_large(self) -> None:
        self.assertEqual(staff_content.MAX_DOCUMENT_BYTES, 500 * 1024 * 1024)
        with self.assertRaisesRegex(ValueError, "selected document is empty"):
            staff_content._validate_document_content(b"")
        with patch.object(staff_content, "MAX_DOCUMENT_BYTES", 3):
            with self.assertRaisesRegex(ValueError, "maximum allowed size is 0 MB"):
                staff_content._validate_document_content(b"four")

    def test_student_can_remove_only_their_own_shared_document_access(self) -> None:
        with (
            patch.object(staff_content, "DATA_DIR", self.root),
            patch.object(staff_content, "DOCUMENTS_PATH", self.root / "documents.json"),
            patch.object(staff_content, "DOCUMENT_DIR", self.root / "documents"),
        ):
            record = staff_content.save_document(
                "school-guide.txt",
                b"Guide",
                "Student Services",
                "staff-1",
                ["student-1", "student-2"],
            )
            with (
                patch.object(auth, "is_student", return_value=True),
                patch.object(auth, "get_current_user_id", return_value="STUDENT-1"),
            ):
                self.assertTrue(
                    staff_content.remove_shared_document_for_student(
                        record["id"], "student-1"
                    )
                )
            self.assertEqual(staff_content.documents_for_student("student-1"), [])
            self.assertEqual(
                staff_content.documents_for_student("student-2")[0]["id"],
                record["id"],
            )
            with (
                patch.object(auth, "is_student", return_value=True),
                patch.object(auth, "get_current_user_id", return_value="student-1"),
                self.assertRaises(PermissionError),
            ):
                staff_content.remove_shared_document_for_student(
                    record["id"], "student-2"
                )
            with (
                patch.object(auth, "is_student", return_value=False),
                patch.object(auth, "get_current_user_id", return_value="staff-1"),
                self.assertRaises(PermissionError),
            ):
                staff_content.remove_shared_document_for_student(
                    record["id"], "student-1"
                )

    def test_staff_can_delete_shared_document_and_revoke_all_access(self) -> None:
        document_dir = self.root / "documents"
        with (
            patch.object(staff_content, "DATA_DIR", self.root),
            patch.object(staff_content, "DOCUMENTS_PATH", self.root / "documents.json"),
            patch.object(staff_content, "DOCUMENT_DIR", document_dir),
        ):
            record = staff_content.save_document(
                "school-guide.txt",
                b"Guide",
                "Student Services",
                "staff-1",
                ["student-1", "student-2"],
            )
            stored_path = document_dir / record["stored_name"]
            self.assertTrue(stored_path.is_file())

            with (
                patch.object(auth, "is_staff", return_value=True),
                patch.object(auth, "is_student", return_value=False),
            ):
                self.assertTrue(staff_content.delete_document(record["id"]))

            self.assertFalse(stored_path.exists())
            self.assertEqual(staff_content.load_documents(), [])
            self.assertEqual(staff_content.documents_for_student("student-1"), [])
            self.assertEqual(staff_content.documents_for_student("student-2"), [])
            with (
                patch.object(auth, "is_staff", return_value=False),
                self.assertRaises(PermissionError),
            ):
                staff_content.delete_document(record["id"])

    def test_analytics_report_history_and_saved_exports(self) -> None:
        report_dir = self.root / "reports"
        history_path = report_dir / "history.json"
        with (
            patch.object(analytics_reports, "REPORT_DIR", report_dir),
            patch.object(analytics_reports, "HISTORY_PATH", history_path),
        ):
            record = analytics_reports.save_report(
                "Student Inquiry Report",
                "Student Inquiry Report",
                "staff-1",
                {"csv": b"question\nHow do I enroll?\n", "pdf": analytics_reports.make_pdf("Report", ["One row"])},
            )
            self.assertEqual(analytics_reports.load_history()[0]["id"], record["id"])
            self.assertEqual(
                analytics_reports.read_report_file(record["files"]["csv"]),
                b"question\nHow do I enroll?\n",
            )
            self.assertTrue(analytics_reports.read_report_file(record["files"]["pdf"]).startswith(b"%PDF-1.4"))

    def test_report_pdf_splits_large_reports_into_pages(self) -> None:
        pdf = analytics_reports.make_pdf("Activity", [f"Record {index}" for index in range(120)])
        self.assertTrue(pdf.startswith(b"%PDF-1.4"))
        self.assertIn(b"/Count 3", pdf)


if __name__ == "__main__":
    unittest.main()
