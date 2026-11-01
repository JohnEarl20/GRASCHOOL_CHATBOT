"use client";

import { FormEvent, useCallback, useEffect, useRef, useState } from "react";
import type { User } from "@supabase/supabase-js";
import { createSupabaseBrowserClient } from "@/lib/supabase";

type Profile = { id: string; student_id: string; full_name: string; role: "student" | "staff"; preferences?: { answer_threshold?: number } };
type Message = { id: string; role: "student" | "assistant" | "staff"; content: string; created_at: string };
type Conversation = { id: string; title: string; updated_at: string };
type View = "chat" | "voice" | "dashboard" | "settings";

export default function Home() {
  const [supabase] = useState(() => {
    try { return createSupabaseBrowserClient(); } catch { return null; }
  });
  const [user, setUser] = useState<User | null>(null);
  const [profile, setProfile] = useState<Profile | null>(null);
  const [mode, setMode] = useState<"login" | "register">("login");
  const [view, setView] = useState<View>("chat");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [studentId, setStudentId] = useState("");
  const [fullName, setFullName] = useState("");
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [activeConversation, setActiveConversation] = useState<string | null>(null);
  const [messages, setMessages] = useState<Message[]>([]);
  const [draft, setDraft] = useState("");
  const [sending, setSending] = useState(false);
  const [recordingUrl, setRecordingUrl] = useState("");
  const [recording, setRecording] = useState(false);
  const [summary, setSummary] = useState<{ total: number; answered: number; recent: Message[] } | null>(null);
  const [threshold, setThreshold] = useState(0.6);
  const mediaRecorder = useRef<MediaRecorder | null>(null);
  const chunks = useRef<BlobPart[]>([]);
  const messagesEnd = useRef<HTMLDivElement>(null);

  const loadAccount = useCallback(async (nextUser: User | null) => {
    setUser(nextUser);
    if (!nextUser || !supabase) {
      setProfile(null);
      setLoading(false);
      return;
    }
    const { data } = await supabase.from("profiles").select("id, student_id, full_name, role, preferences").eq("id", nextUser.id).single();
    const nextProfile = data as Profile | null;
    setProfile(nextProfile);
    if (typeof nextProfile?.preferences?.answer_threshold === "number") setThreshold(nextProfile.preferences.answer_threshold);
    setLoading(false);
  }, [supabase]);

  useEffect(() => {
    if (!supabase) {
      const timer = window.setTimeout(() => setLoading(false), 0);
      return () => window.clearTimeout(timer);
    }
    supabase.auth.getUser().then(({ data }) => loadAccount(data.user));
    const { data: listener } = supabase.auth.onAuthStateChange((_event, session) => {
      void loadAccount(session?.user ?? null);
    });
    return () => listener.subscription.unsubscribe();
  }, [loadAccount, supabase]);

  const loadConversations = useCallback(async () => {
    if (!supabase || !user) return;
    const { data, error: queryError } = await supabase
      .from("conversations").select("id, title, updated_at").order("updated_at", { ascending: false });
    if (queryError) { setError(queryError.message); return; }
    const rows = (data ?? []) as Conversation[];
    setConversations(rows);
    setActiveConversation((current) => current && rows.some((row) => row.id === current) ? current : rows[0]?.id ?? null);
  }, [supabase, user]);

  useEffect(() => {
    const timer = window.setTimeout(() => void loadConversations(), 0);
    return () => window.clearTimeout(timer);
  }, [loadConversations]);

  useEffect(() => {
    if (!supabase || !activeConversation) {
      const timer = window.setTimeout(() => setMessages([]), 0);
      return () => window.clearTimeout(timer);
    }
    let active = true;
    supabase.from("messages").select("id, role, content, created_at").eq("conversation_id", activeConversation)
      .order("created_at").then(({ data, error: queryError }) => {
        if (!active) return;
        if (queryError) setError(queryError.message);
        else setMessages((data ?? []) as Message[]);
      });
    return () => { active = false; };
  }, [activeConversation, supabase]);

  useEffect(() => { messagesEnd.current?.scrollIntoView({ behavior: "smooth" }); }, [messages]);

  async function submitAuth(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!supabase) return;
    setError("");
    setLoading(true);
    if (mode === "login") {
      const { error: authError } = await supabase.auth.signInWithPassword({ email, password });
      if (authError) { setError(authError.message); setLoading(false); }
      return;
    }
    const { data, error: authError } = await supabase.auth.signUp({
      email, password, options: { data: { student_id: studentId.trim(), full_name: fullName.trim() } },
    });
    if (authError) { setError(authError.message); setLoading(false); return; }
    if (!data.session) {
      setError("Nagawa ang account. Tingnan ang email para kumpirmahin bago mag-login.");
      setLoading(false);
    }
  }

  async function sendMessage(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!supabase || !user || !draft.trim() || sending) return;
    setSending(true);
    setError("");
    const text = draft.trim();
    setDraft("");
    const optimistic: Message = { id: crypto.randomUUID(), role: "student", content: text, created_at: new Date().toISOString() };
    setMessages((current) => [...current, optimistic]);
    try {
      const { data: sessionData } = await supabase.auth.getSession();
      const response = await fetch("/api/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json", Authorization: `Bearer ${sessionData.session?.access_token ?? ""}` },
        body: JSON.stringify({ conversationId: activeConversation, text }),
      });
      const result = await response.json();
      if (!response.ok) throw new Error(result.error ?? "Hindi naipadala ang mensahe.");
      setActiveConversation(result.conversationId);
      await loadConversations();
      const { data, error: queryError } = await supabase.from("messages")
        .select("id, role, content, created_at").eq("conversation_id", result.conversationId).order("created_at");
      if (queryError) throw queryError;
      setMessages((data ?? []) as Message[]);
    } catch (caught) {
      setMessages((current) => current.filter((message) => message.id !== optimistic.id));
      setDraft(text);
      setError(caught instanceof Error ? caught.message : "Hindi naipadala ang mensahe.");
    } finally { setSending(false); }
  }

  async function newConversation() {
    if (!supabase) return;
    const { data, error: insertError } = await supabase.from("conversations").insert({ title: "Bagong usapan" }).select("id").single();
    if (insertError) { setError(insertError.message); return; }
    setConversations((current) => [{ id: data.id, title: "Bagong usapan", updated_at: new Date().toISOString() }, ...current]);
    setMessages([]);
    setActiveConversation(data.id);
  }

  async function logout() { await supabase?.auth.signOut(); setConversations([]); setMessages([]); }

  async function toggleRecording() {
    if (recording && mediaRecorder.current) { mediaRecorder.current.stop(); setRecording(false); return; }
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      const recorder = new MediaRecorder(stream);
      chunks.current = [];
      recorder.ondataavailable = (event) => { if (event.data.size) chunks.current.push(event.data); };
      recorder.onstop = () => {
        setRecordingUrl(URL.createObjectURL(new Blob(chunks.current, { type: recorder.mimeType || "audio/webm" })));
        stream.getTracks().forEach((track) => track.stop());
      };
      recorder.start();
      mediaRecorder.current = recorder;
      setRecording(true);
    } catch { setError("Hindi ma-access ang mikropono. Payagan ang microphone permission o mag-upload ng audio file."); }
  }

  async function loadDashboard() {
    if (!supabase || !profile || profile.role !== "staff") return;
    const { data, error: queryError } = await supabase.from("chat_events").select("answered, created_at").order("created_at", { ascending: false }).limit(500);
    if (queryError) { setError(queryError.message); return; }
    const rows = data ?? [];
    setSummary({ total: rows.length, answered: rows.filter((row) => row.answered).length, recent: [] });
  }

  async function saveThreshold() {
    if (!supabase) return;
    const { error: updateError } = await supabase.from("profiles").update({ preferences: { answer_threshold: threshold } }).eq("id", user?.id);
    if (updateError) setError(updateError.message);
    else setError("Na-save ang preference.");
  }

  if (loading) return <main className="center-screen"><div className="spinner" /><p>Inihahanda ang GRA SCHOOL assistant…</p></main>;
  if (!supabase) return <main className="center-screen"><section className="auth-card"><Logo /><h1>Kailangan ng setup</h1><p>I-configure ang Supabase URL at anon key sa environment variables ng Vercel.</p></section></main>;
  if (!user || !profile) return (
    <main className="auth-screen">
      <section className="auth-card">
        <Logo />
        <p className="eyebrow">COGNITIVE CAMPUS ASSISTANT</p>
        <h1>{mode === "login" ? "Magandang araw." : "Gumawa ng student account"}</h1>
        <p className="muted">{mode === "login" ? "Mag-login para magtanong sa registrar assistant." : "Gamitin ang iyong email para sa ligtas na pag-login."}</p>
        <form className="form-stack" onSubmit={submitAuth}>
          {mode === "register" && <>
            <label>Buong pangalan<input required value={fullName} onChange={(event) => setFullName(event.target.value)} autoComplete="name" /></label>
            <label>Student ID<input required value={studentId} onChange={(event) => setStudentId(event.target.value)} /></label>
          </>}
          <label>Email<input required type="email" value={email} onChange={(event) => setEmail(event.target.value)} autoComplete="email" /></label>
          <label>Password<input required type="password" minLength={8} value={password} onChange={(event) => setPassword(event.target.value)} autoComplete={mode === "login" ? "current-password" : "new-password"} /></label>
          {error && <p className="error">{error}</p>}
          <button className="primary-button" disabled={loading}>{mode === "login" ? "Mag-login" : "Gumawa ng account"}</button>
        </form>
        <button className="text-button" onClick={() => { setError(""); setMode(mode === "login" ? "register" : "login"); }}>
          {mode === "login" ? "Wala pang account? Mag-register" : "May account na? Mag-login"}
        </button>
        <p className="small-note">Student account muna ang bagong registration. Staff access ay itinatalaga ng administrator.</p>
      </section>
    </main>
  );

  return (
    <main className="app-shell">
      <aside className="sidebar">
        <Logo />
        <div className="profile-chip"><span className="avatar">{(profile.full_name || "S").slice(0, 1).toUpperCase()}</span><div><strong>{profile.full_name}</strong><small>{profile.role === "staff" ? "Registrar Staff" : `Student · ${profile.student_id}`}</small></div></div>
        <nav className="nav-list">
          <button className={view === "chat" ? "nav-item active" : "nav-item"} onClick={() => setView("chat")}>✦ <span>AI Assistant</span></button>
          <button className={view === "voice" ? "nav-item active" : "nav-item"} onClick={() => setView("voice")}>◉ <span>Voice Upload</span></button>
          {profile.role === "staff" && <button className={view === "dashboard" ? "nav-item active" : "nav-item"} onClick={() => { setView("dashboard"); void loadDashboard(); }}>▦ <span>Staff Dashboard</span></button>}
          <button className={view === "settings" ? "nav-item active" : "nav-item"} onClick={() => setView("settings")}>⚙ <span>Settings</span></button>
        </nav>
        <div className="sidebar-bottom"><p>Student services · English · Filipino · Taglish</p><button className="text-button" onClick={logout}>Mag-log out</button></div>
      </aside>
      <section className="workspace">
        <header className="topbar"><div><span className="status-dot" />GRA SCHOOL <span className="muted">/ {view === "chat" ? "AI Assistant" : view === "voice" ? "Voice Upload" : view === "dashboard" ? "Staff Dashboard" : "Settings"}</span></div><span className="online-label">● Online</span></header>
        {error && <div className="toast-error">{error}<button onClick={() => setError("")}>×</button></div>}
        {view === "chat" && <div className="chat-layout">
          <aside className="conversation-list"><div className="list-heading"><strong>Mga usapan</strong><button className="icon-button" onClick={newConversation} aria-label="Bagong usapan">＋</button></div>
            {conversations.map((conversation) => <button key={conversation.id} className={conversation.id === activeConversation ? "conversation-link selected" : "conversation-link"} onClick={() => setActiveConversation(conversation.id)}>{conversation.title}<small>{new Date(conversation.updated_at).toLocaleDateString()}</small></button>)}
            {!conversations.length && <p className="small-note">Wala pang usapan. Magtanong sa ibaba para magsimula.</p>}
          </aside>
          <section className="chat-panel"><div className="chat-title"><div><p className="eyebrow">REGISTRAR SUPPORT</p><h1>AI Assistant</h1></div><span className="confidence-chip">Explainable answers</span></div>
            <div className="message-list">
              {!messages.length && <div className="welcome-card"><div className="welcome-icon">✦</div><h2>Kumusta, {profile.full_name.split(" ")[0]}!</h2><p>Magtanong tungkol sa enrollment requirements, deadlines, fees, office hours, prerequisites, o clearance.</p><div className="suggestions">{["Ano ang kailangan para mag-enroll bilang freshman?", "Kailan ang deadline ng enrollment?", "Saan ang Registrar's Office?"].map((item) => <button key={item} onClick={() => setDraft(item)}>{item}</button>)}</div></div>}
              {messages.map((message) => <article key={message.id} className={`message ${message.role}`}><span className="message-label">{message.role === "student" ? "Ikaw" : message.role === "staff" ? "Registrar Staff" : "GRA Assistant"}</span><p>{message.content}</p></article>)}
              {sending && <article className="message assistant"><span className="message-label">GRA Assistant</span><p className="typing">Nag-iisip…</p></article>}
              <div ref={messagesEnd} />
            </div>
            <form className="composer" onSubmit={sendMessage}><textarea value={draft} onChange={(event) => setDraft(event.target.value)} placeholder="I-type ang tanong mo dito…" rows={2} onKeyDown={(event) => { if (event.key === "Enter" && !event.shiftKey) { event.preventDefault(); event.currentTarget.form?.requestSubmit(); } }} /><button className="send-button" disabled={!draft.trim() || sending}>Ipadala ↑</button><small>Huwag ilagay ang password o personal na impormasyon. Enter para ipadala · Shift+Enter para bagong linya.</small></form>
          </section>
        </div>}
        {view === "voice" && <section className="content-page"><p className="eyebrow">RECORD & PLAY</p><h1>Voice Upload</h1><p className="muted">Mag-record o mag-upload ng audio para mapakinggan. Walang speech-to-text; i-type ang tanong sa AI Assistant.</p><div className="voice-card"><button className={recording ? "record-button recording" : "record-button"} onClick={toggleRecording}>{recording ? "■ Ihinto ang recording" : "● Magsimulang mag-record"}</button><label className="upload-button">Mag-upload ng audio<input type="file" accept="audio/*" onChange={(event) => { const file = event.target.files?.[0]; if (file) setRecordingUrl(URL.createObjectURL(file)); }} /></label>{recordingUrl && <audio controls src={recordingUrl} />}</div></section>}
        {view === "dashboard" && <section className="content-page"><p className="eyebrow">STAFF ONLY</p><h1>Staff Dashboard</h1>{profile.role !== "staff" ? <p className="error">Walang pahintulot sa staff dashboard.</p> : <><p className="muted">Chat activity at response status sa database.</p><div className="metrics"><div><small>Chat events</small><strong>{summary?.total ?? "—"}</strong></div><div><small>Nasagot</small><strong>{summary ? `${summary.answered}` : "—"}</strong></div><div><small>Answer rate</small><strong>{summary && summary.total ? `${Math.round(summary.answered / summary.total * 100)}%` : "—"}</strong></div></div><button className="secondary-button" onClick={() => void loadDashboard()}>I-refresh ang metrics</button></>}</section>}
        {view === "settings" && <section className="content-page"><p className="eyebrow">PREFERENCES</p><h1>Settings</h1><p className="muted">Account: {user.email} · {profile.role === "staff" ? "Staff" : "Student"}</p><div className="settings-card"><label>Answer confidence threshold <strong>{Math.round(threshold * 100)}%</strong><input type="range" min="40" max="90" value={Math.round(threshold * 100)} onChange={(event) => setThreshold(Number(event.target.value) / 100)} /></label><button className="secondary-button" onClick={() => void saveThreshold()}>I-save ang preference</button><small>Nai-save ang preference sa iyong profile; ang chat ay gumagamit pa ng default policy sa kasalukuyan.</small></div></section>}
      </section>
    </main>
  );
}

function Logo() { return <div className="brand"><span className="brand-mark">G</span><div><strong>GRA SCHOOL</strong><small>COGNITIVE CAMPUS</small></div></div>; }
