create table if not exists public.profiles (
  id uuid primary key references auth.users(id) on delete cascade,
  student_id text not null unique,
  full_name text not null default '',
  role text not null default 'student' check (role in ('student', 'staff')),
  preferences jsonb not null default '{"answer_threshold":0.6}'::jsonb,
  created_at timestamptz not null default now()
);
alter table public.profiles add constraint profiles_student_id_not_empty check (length(trim(student_id)) > 0);

create table if not exists public.conversations (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references auth.users(id) on delete cascade,
  title text not null default 'Bagong usapan',
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table if not exists public.messages (
  id uuid primary key default gen_random_uuid(),
  conversation_id uuid not null references public.conversations(id) on delete cascade,
  user_id uuid not null references auth.users(id) on delete cascade,
  role text not null check (role in ('student', 'assistant', 'staff')),
  content text not null check (char_length(content) <= 5000),
  created_at timestamptz not null default now()
);

create table if not exists public.chat_events (
  id bigint generated always as identity primary key,
  user_id uuid not null references auth.users(id) on delete cascade,
  conversation_id uuid not null references public.conversations(id) on delete cascade,
  intent text not null,
  confidence real not null check (confidence between 0 and 1),
  answered boolean not null,
  source text not null,
  created_at timestamptz not null default now()
);

create or replace function public.is_staff()
returns boolean language sql stable security definer set search_path = public
as $$ select exists (select 1 from public.profiles where id = auth.uid() and role = 'staff') $$;

create or replace function public.current_profile_role()
returns text language sql stable security definer set search_path = public
as $$ select role from public.profiles where id = auth.uid() $$;

create or replace function public.create_profile_for_new_user()
returns trigger language plpgsql security definer set search_path = public
as $$
begin
  insert into public.profiles (id, student_id, full_name)
  values (
    new.id,
    trim(coalesce(new.raw_user_meta_data->>'student_id', '')),
    trim(coalesce(new.raw_user_meta_data->>'full_name', ''))
  );
  return new;
end;
$$;

drop trigger if exists create_profile_after_signup on auth.users;
create trigger create_profile_after_signup
after insert on auth.users
for each row execute procedure public.create_profile_for_new_user();

alter table public.profiles enable row level security;
alter table public.conversations enable row level security;
alter table public.messages enable row level security;
alter table public.chat_events enable row level security;

create policy "Read own profile or staff profiles" on public.profiles
for select to authenticated using (id = auth.uid() or public.is_staff());
create policy "Update own profile preferences" on public.profiles
for update to authenticated using (id = auth.uid())
with check (id = auth.uid() and role = public.current_profile_role());

create policy "Read own or staff conversations" on public.conversations
for select to authenticated using (user_id = auth.uid() or public.is_staff());
create policy "Create own conversations" on public.conversations
for insert to authenticated with check (user_id = auth.uid());
create policy "Update own or staff conversations" on public.conversations
for update to authenticated using (user_id = auth.uid() or public.is_staff()) with check (user_id = auth.uid() or public.is_staff());

create policy "Read own or staff messages" on public.messages
for select to authenticated using (
  public.is_staff() or exists (
    select 1 from public.conversations c where c.id = conversation_id and c.user_id = auth.uid()
  )
);
create policy "Students send own messages" on public.messages
for insert to authenticated with check (
  role = 'student' and user_id = auth.uid() and exists (
    select 1 from public.conversations c where c.id = conversation_id and c.user_id = auth.uid()
  )
);
create policy "Staff reply to conversations" on public.messages
for insert to authenticated with check (role = 'staff' and user_id = auth.uid() and public.is_staff());

create policy "Staff read chat events" on public.chat_events
for select to authenticated using (public.is_staff());

grant select on public.profiles to authenticated;
grant update (full_name, preferences) on public.profiles to authenticated;
grant select, insert, update on public.conversations to authenticated;
grant select, insert on public.messages to authenticated;
grant select on public.chat_events to authenticated;
