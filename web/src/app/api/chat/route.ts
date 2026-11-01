import { NextResponse } from "next/server";
import { createClient } from "@supabase/supabase-js";
import model from "@/intent-model.json";
import ontology from "@/data-ontology.json";

type IntentModel = {
  vocabulary: Record<string, number>;
  idf: number[];
  classes: string[];
  coef: number[][];
  intercept: number[];
};
type RecordData = Record<string, unknown>;
type OntologyData = {
  meta: { school: string };
  requirements: RecordData[];
  deadlines: RecordData[];
  fees: RecordData[];
  offices: RecordData[];
  courses: RecordData[];
  programs: RecordData[];
  services: RecordData[];
};
type ChatFacts = { studentType?: string; held: Set<string>; missing: Set<string>; feesPaid?: boolean };

const intentModel = model as IntentModel;
const knowledge = ontology as OntologyData;
const particles = new Set("po ba baka kasi naman sana pre sis dong daw pala rin lang nga opo ah eh oh ay yung mga natin ninyo kayo ako ikaw ito iyon para kung sige nako tulong yep nope pro fyi pls tnx thx kk lg mgd hmm mismo talaga".split(" "));
const documents: Record<string, string[]> = {
  form138: ["form 138", "form138", "school record"],
  psa_birth_certificate: ["psa birth certificate", "birth certificate", "psa"],
  tor: ["transcript of records", "transcript", "tor", "tsr"],
  honorable_dismissal: ["honorable dismissal", "good moral character"],
  clearance: ["clearance"],
};

function normalize(text: string) {
  return text.toLowerCase().replace(/['’]/g, "").replace(/[^a-z0-9\s]/g, " ")
    .split(/\s+/).filter((word) => word && !particles.has(word)).join(" ");
}

function predict(text: string) {
  const words = normalize(text).match(/[a-z0-9_]{2,}/g) ?? [];
  const counts = new Map<string, number>();
  for (const word of words) counts.set(word, (counts.get(word) ?? 0) + 1);
  for (let index = 0; index + 1 < words.length; index++) {
    const bigram = `${words[index]} ${words[index + 1]}`;
    counts.set(bigram, (counts.get(bigram) ?? 0) + 1);
  }
  const vector: [number, number][] = [];
  for (const [feature, count] of counts) {
    const featureIndex = intentModel.vocabulary[feature];
    if (featureIndex !== undefined) vector.push([featureIndex, (1 + Math.log(count)) * intentModel.idf[featureIndex]]);
  }
  const norm = Math.sqrt(vector.reduce((sum, [, value]) => sum + value * value, 0));
  const scores = intentModel.classes.map((name, classIndex) => ({
    name,
    score: intentModel.intercept[classIndex] + vector.reduce(
      (sum, [featureIndex, value]) => sum + value / (norm || 1) * intentModel.coef[classIndex][featureIndex], 0,
    ),
  }));
  const maxScore = Math.max(...scores.map((item) => item.score));
  const denominator = scores.reduce((sum, item) => sum + Math.exp(item.score - maxScore), 0);
  return scores.map((item) => ({ name: item.name, probability: Math.exp(item.score - maxScore) / denominator }))
    .sort((left, right) => right.probability - left.probability);
}

function collectFacts(texts: string[]): ChatFacts {
  const facts: ChatFacts = { held: new Set(), missing: new Set() };
  for (const text of texts) {
    const lower = text.toLowerCase().replace(/['’]/g, "");
    if (/\b(freshman|freshmen|first year|new student|bagong student)\b/.test(lower)) facts.studentType = "freshman";
    if (/\b(transferee|transfer student)\b/.test(lower)) facts.studentType = "transferee";
    if (/\b(returning student|returnee|old student)\b/.test(lower)) facts.studentType = "returning";
    const fragments = lower.split(/[.?!,;]+/).map((fragment) => fragment.trim()).filter(Boolean);
    for (const fragment of fragments) {
      if (/^(do|does|did|can|could|is|are|am|what|when|where|why|how|which|who|bakit|saan|kailan|ano)\b/.test(fragment)) continue;
      for (const [document, aliases] of Object.entries(documents)) {
        if (!aliases.some((alias) => fragment.includes(alias))) continue;
        const position = Math.max(...aliases.map((alias) => fragment.lastIndexOf(alias)));
        const prefix = fragment.slice(Math.max(0, position - 28), position);
        if (/\b(no|not|without|missing|lack|wala|walang|hindi|di|dont|doesnt|need|kailangan)\b/.test(prefix)) {
          facts.missing.add(document);
          facts.held.delete(document);
        } else {
          facts.held.add(document);
          facts.missing.delete(document);
        }
      }
    }
    if (/\b(unpaid|not paid|hindi pa bayad|wala pang bayad)\b/.test(lower)) facts.feesPaid = false;
    else if (/\b(paid|bayad|payment)\b/.test(lower)) facts.feesPaid = true;
  }
  return facts;
}

const str = (record: RecordData, key: string) => String(record[key] ?? "");
const array = (record: RecordData, key: string) => Array.isArray(record[key]) ? record[key] as unknown[] : [];
function answer(intent: string, text: string, facts: ChatFacts) {
  if (intent === "greet") return `**Good day from ${knowledge.meta.school}!**\n\nI can help with enrollment requirements, deadlines, fees, office hours, prerequisites, and clearance. Please do not share passwords or personal details here.`;
  if (intent === "ask_requirements") {
    const requirements = facts.studentType
      ? knowledge.requirements.filter((record) => array(record, "applies_to").includes(facts.studentType))
      : knowledge.requirements;
    if (!requirements.length) return "I do not have a requirement list for that student type yet.";
    return `**Documents for ${facts.studentType ?? "each student type"}:**\n\n${requirements.map((record) => `- **${str(record, "name")}** — ${str(record, "description")} (${array(record, "applies_to").join(", ")})`).join("\n")}\n\nWhere: ${str(knowledge.offices[0], "name")} — ${str(knowledge.offices[0], "location")}.`;
  }
  if (intent === "ask_schedule_deadline") {
    const keyword = ["class", "payment", "scholarship", "add", "drop", "enrollment"].find((word) => text.toLowerCase().includes(word));
    const rows = keyword ? knowledge.deadlines.filter((item) => str(item, "label").toLowerCase().includes(keyword)) : knowledge.deadlines;
    const deadlines = rows.length ? rows : knowledge.deadlines;
    return `**Enrollment dates for this term:**\n\n${deadlines.map((item) => `- ${str(item, "label")}: ${str(item, "date")}${item.confirmed ? "" : " (not confirmed yet)"}`).join("\n")}\n\nEnrollment is at the Registrar's Office, Main Building Room 101.`;
  }
  if (intent === "ask_fees_payment") return `**Assessment fees (confirm amounts with the Cashier):**\n\n${knowledge.fees.map((fee) => `- ${str(fee, "label")}: PHP ${Number(fee.amount).toLocaleString()}`).join("\n")}\n\nPayment options: ${array(knowledge.fees[0], "payment_options").join(", ")}.`;
  if (intent === "ask_office_hours_location") {
    const askedOffice = ["registrar", "cashier", "guidance", "library", "osa", "clinic"].find((office) => text.toLowerCase().includes(office));
    const offices = askedOffice ? knowledge.offices.filter((office) => str(office, "id") === askedOffice) : knowledge.offices;
    return `**Office information:**\n\n${offices.map((office) => `- **${str(office, "name")}** — ${str(office, "location")}\n  - Hours: ${str(office, "hours")}\n  - Handles: ${array(office, "handles").join(", ")}`).join("\n")}`;
  }
  if (intent === "ask_course_prereq") {
    const code = text.match(/\b([A-Za-z]{2,5})\s*(?:ELEC\s*)?(\d{1,3})\b/i);
    const picked = code ? knowledge.courses.filter((course) => str(course, "code").replace(/\s/g, "").toLowerCase() === `${code[1]}${code[2]}`.toLowerCase()) : [];
    const courses = picked.length ? picked : knowledge.courses;
    return `**Course information:**\n\n${courses.map((course) => `- **${str(course, "code")} ${str(course, "title")}** (${str(course, "units")} units)\n  - Prerequisite: ${array(course, "prerequisites").join(", ") || "none"}\n  - Offered in: ${array(course, "offered_in").join(", ")}`).join("\n")}`;
  }
  if (intent === "ask_clearance_process") {
    const service = knowledge.services.find((item) => str(item, "id") === "clearance");
    const guidance = knowledge.offices.find((office) => str(office, "id") === "guidance");
    return `**${str(service ?? {}, "name")} — steps:**\n\n${array(service ?? {}, "steps").map((step, index) => `${index + 1}. ${String(step)}`).join("\n")}\n\nWhere: ${str(guidance ?? {}, "name")} — ${str(guidance ?? {}, "location")}, ${str(guidance ?? {}, "hours")}.`;
  }
  if (intent === "check_eligibility") {
    if (!facts.studentType) return "Para ma-check ang eligibility, sabihin kung freshman, transferee, o returning student ka.";
    const required = facts.studentType === "freshman" ? ["form138", "psa_birth_certificate"] : facts.studentType === "transferee" ? ["tor", "honorable_dismissal"] : ["clearance"];
    const missing = required.filter((document) => !facts.held.has(document));
    if (missing.length) return `**Hindi pa kumpleto ang requirements.**\n\nKulang pa:\n${missing.map((document) => `- ${document.replaceAll("_", " ")}`).join("\n")}\n\nRules fired: R1–R10, R13.`;
    if (facts.feesPaid !== true) return "**Kumpleto ang documents; susunod ang assessment payment.**\n\nKung nakabayad ka na, sabihin ito para ma-update ang check. Rules fired: R1–R10, R12.";
    return "**Handa ka na para sa official enrollment.**\n\nKumpleto ang requirements at naitala ang bayad. Rules fired: R1–R11.";
  }
  if (intent === "request_human") return `**Humingi ng tulong sa Registrar.**\n\n${str(knowledge.offices[0], "name")} — ${str(knowledge.offices[0], "location")}\n${str(knowledge.offices[0], "hours")}`;
  if (intent === "give_feedback") return "Salamat sa feedback mo. Naitala ito para matingnan ng registrar staff.";
  return "Hindi ako sigurado sa tanong na iyan. Subukan magtanong tungkol sa requirements, deadlines, fees, office hours, prerequisites, o clearance.";
}

export async function POST(request: Request) {
  const url = process.env.NEXT_PUBLIC_SUPABASE_URL;
  const serviceKey = process.env.SUPABASE_SERVICE_ROLE_KEY;
  const accessToken = request.headers.get("authorization")?.replace(/^Bearer\s+/i, "");
  if (!url || !serviceKey) return NextResponse.json({ error: "Hindi pa naka-configure ang database service." }, { status: 503 });
  if (!accessToken) return NextResponse.json({ error: "Kailangan mag-login." }, { status: 401 });
  const admin = createClient(url, serviceKey, { auth: { persistSession: false } });
  const { data: authData, error: authError } = await admin.auth.getUser(accessToken);
  if (authError || !authData.user) return NextResponse.json({ error: "Hindi valid ang login session." }, { status: 401 });

  const body = await request.json().catch(() => null) as { conversationId?: string; text?: string } | null;
  const text = body?.text?.trim();
  if (!text || text.length > 2000) return NextResponse.json({ error: "Maglagay ng tanong na hanggang 2,000 character." }, { status: 400 });
  let conversationId = body?.conversationId;
  if (conversationId) {
    const { data: existing, error } = await admin.from("conversations").select("id").eq("id", conversationId).eq("user_id", authData.user.id).maybeSingle();
    if (error || !existing) return NextResponse.json({ error: "Hindi makita ang usapan." }, { status: 404 });
  } else {
    const { data: created, error } = await admin.from("conversations").insert({ user_id: authData.user.id, title: text.slice(0, 64) }).select("id").single();
    if (error || !created) return NextResponse.json({ error: "Hindi makagawa ng usapan." }, { status: 500 });
    conversationId = created.id;
  }
  const { data: existingMessages } = await admin.from("messages").select("id").eq("conversation_id", conversationId).limit(1);
  if (!existingMessages?.length) {
    await admin.from("conversations").update({ title: text.slice(0, 64) }).eq("id", conversationId);
  }
  const { error: studentMessageError } = await admin.from("messages").insert({
    conversation_id: conversationId, user_id: authData.user.id, role: "student", content: text,
  });
  if (studentMessageError) return NextResponse.json({ error: "Hindi na-save ang tanong." }, { status: 500 });

  const { data: previousMessages } = await admin.from("messages").select("content").eq("conversation_id", conversationId).eq("role", "student").order("created_at");
  const ranked = predict(text);
  const best = ranked[0];
  const runnerUp = ranked[1];
  const confidence = best?.probability ?? 0;
  const decisive = confidence - (runnerUp?.probability ?? 0) >= 0.25;
  const facts = collectFacts((previousMessages ?? []).map((message) => message.content));
  let reply = confidence < 0.4
    ? answer("fallback", text, facts)
    : confidence < 0.6 && !decisive && best.name !== "check_eligibility"
      ? `Hindi ako sigurado kung ano ang tinutukoy mo. ${best.name.replaceAll("_", " ")} ang pinakamalapit na paksa ko.`
      : answer(best.name, text, facts);
  if (!text) reply = "Pakisubukang muli.";
  const { error: assistantMessageError } = await admin.from("messages").insert({
    conversation_id: conversationId, user_id: authData.user.id, role: "assistant", content: reply,
  });
  if (assistantMessageError) return NextResponse.json({ error: "Nasagot ang tanong pero hindi na-save ang sagot." }, { status: 500 });
  const { error: logError } = await admin.from("chat_events").insert({
    user_id: authData.user.id, conversation_id: conversationId, intent: best?.name ?? "unknown",
    confidence, answered: confidence >= 0.4, source: best?.name.startsWith("ask_") ? "ontology" : "assistant",
  });
  if (logError) console.error("chat event logging failed", logError.message);
  return NextResponse.json({ conversationId, confidence });
}
