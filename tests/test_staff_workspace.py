from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import tempfile
import unittest
from unittest.mock import patch

from code import analytics_reports, auth, conversation, dialogue, knowledge, logger, staff_content


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
            patch.object(auth, "is_staff", return_value=False),
        ):
            created, message = auth.create_account("new-staff", "password", role="staff")
            self.assertFalse(created)
            self.assertIn("authenticated staff", message)
            self.assertFalse((self.root / "users.json").exists())

    def test_authenticated_staff_can_provision_another_staff_account(self) -> None:
        with (
            patch.object(auth, "DATA_DIR", self.root),
            patch.object(auth, "USERS_FILE", self.root / "users.json"),
            patch.object(auth, "is_staff", return_value=True),
        ):
            created, _ = auth.create_account("new-staff", "password", role="staff")
            self.assertTrue(created)
            self.assertEqual(auth._load_users()["new-staff"]["role"], "staff")

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
            self.assertTrue((conversations_dir / f"{created['session_id']}.json").exists())
            self.assertEqual(conversation.get_closed_conversations()[0]["status"], "closed")

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
                "..\\registrar.txt", b"first version", "Registrar", "staff-1"
            )
            replaced = staff_content.replace_document(
                created["id"], "updated.txt", b"updated version", "Registrar", "staff-1"
            )
            record, content = staff_content.read_document(replaced["id"])
            self.assertEqual(record["filename"], "updated.txt")
            self.assertEqual(content, b"updated version")
            self.assertRegex(record["stored_name"], r"^[a-f0-9]{32}\.txt$")

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
