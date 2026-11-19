-- Run once in a dedicated Supabase pilot project. All tables have RLS.
begin;
create table public.pilot_accounts (
 user_id uuid primary key references auth.users(id) on delete cascade,
 credits integer not null default 0 check (credits >= 0),
 created_at timestamptz not null default now()
);
create table public.pilot_inventory (
 user_id uuid primary key references auth.users(id) on delete cascade,
 tools jsonb not null default '[]', revision integer not null default 1,
 updated_at timestamptz not null default now()
);
create table public.pilot_checks (
 id uuid primary key, user_id uuid not null references auth.users(id) on delete cascade,
 question text not null, result jsonb not null, created_at timestamptz not null default now()
);
create table public.pilot_usage (
 id uuid primary key, user_id uuid not null references auth.users(id) on delete cascade,
 status text not null check(status in ('reserved','completed','released')),
 fingerprint text not null check(length(fingerprint)=64),
 created_at timestamptz not null default now()
);
create table public.pilot_orders (
 session_id text primary key, user_id uuid not null references auth.users(id) on delete cascade,
 request_id uuid not null, amount integer not null check(amount>0), currency text not null check(currency='usd'),
 credits integer not null check(credits>0), fulfilled boolean not null default false,
 created_at timestamptz not null default now(), unique(user_id,request_id)
);
alter table public.pilot_accounts enable row level security;
alter table public.pilot_inventory enable row level security;
alter table public.pilot_checks enable row level security;
alter table public.pilot_usage enable row level security;
alter table public.pilot_orders enable row level security;
create policy account_owner on public.pilot_accounts for select to authenticated using(user_id=auth.uid());
create policy inventory_owner_read on public.pilot_inventory for select to authenticated using(user_id=auth.uid());
create policy checks_owner_read on public.pilot_checks for select to authenticated using(user_id=auth.uid());
create policy checks_owner_delete on public.pilot_checks for delete to authenticated using(user_id=auth.uid());
-- No direct credit/order/usage writes, even by authenticated users.
revoke all on public.pilot_accounts, public.pilot_inventory, public.pilot_checks, public.pilot_usage, public.pilot_orders from anon, authenticated;
grant select on public.pilot_accounts, public.pilot_inventory, public.pilot_checks to authenticated;
grant delete on public.pilot_checks to authenticated;
grant all on public.pilot_accounts, public.pilot_inventory, public.pilot_checks, public.pilot_usage, public.pilot_orders to service_role;

create function public.pilot_set_inventory(p_user uuid,p_tools jsonb,p_revision integer) returns jsonb
language plpgsql security definer set search_path=public as $$
declare r public.pilot_inventory;
begin
 if jsonb_typeof(p_tools) <> 'array' or jsonb_array_length(p_tools)>30 then raise exception 'Invalid inventory'; end if;
 insert into pilot_inventory(user_id,tools) values(p_user,p_tools)
 on conflict(user_id) do update set tools=excluded.tools, revision=pilot_inventory.revision+1, updated_at=now()
 where pilot_inventory.revision=p_revision
 returning * into r;
 if not found or (r.revision=1 and p_revision<>0) then raise exception 'Inventory changed; reload first' using errcode='40001'; end if;
 return to_jsonb(r);
end $$;

create function public.pilot_reserve_check(p_user uuid,p_request uuid,p_fingerprint text) returns jsonb
language plpgsql security definer set search_path=public as $$
declare balance integer; previous pilot_usage; saved pilot_checks;
begin
 insert into pilot_accounts(user_id) values(p_user) on conflict do nothing;
 select credits into balance from pilot_accounts where user_id=p_user for update;
 select * into previous from pilot_usage where id=p_request;
 if found then
  if previous.user_id<>p_user or previous.fingerprint<>p_fingerprint then raise exception 'Request conflict'; end if;
  if previous.status='completed' then
   select * into saved from pilot_checks where id=p_request and user_id=p_user;
   return jsonb_build_object('status','completed','result',saved.result);
  end if;
  return jsonb_build_object('status',previous.status);
 end if;
 if balance<1 then return jsonb_build_object('status','no_credits'); end if;
 update pilot_accounts set credits=credits-1 where user_id=p_user;
 insert into pilot_usage(id,user_id,status,fingerprint) values(p_request,p_user,'reserved',p_fingerprint);
 return jsonb_build_object('status','reserved_new');
end $$;

create function public.pilot_release_check(p_user uuid,p_request uuid) returns void
language plpgsql security definer set search_path=public as $$
begin
 -- Same lock order as reservation, completion and payment fulfillment.
 perform 1 from pilot_accounts where user_id=p_user for update;
 update pilot_usage set status='released' where id=p_request and user_id=p_user and status='reserved';
 if found then update pilot_accounts set credits=credits+1 where user_id=p_user; end if;
end $$;

create function public.pilot_complete_check(p_user uuid,p_request uuid,p_question text,p_result jsonb) returns void
language plpgsql security definer set search_path=public as $$
begin
 perform 1 from pilot_accounts where user_id=p_user for update;
 update pilot_usage set status='completed' where id=p_request and user_id=p_user and status='reserved';
 if not found then raise exception 'No active reservation'; end if;
 insert into pilot_checks(id,user_id,question,result) values(p_request,p_user,p_question,p_result);
end $$;

create function public.pilot_fulfill_order(p_session text,p_user uuid,p_amount integer,p_currency text) returns jsonb
language plpgsql security definer set search_path=public as $$
declare r pilot_orders;
begin
 insert into pilot_accounts(user_id) values(p_user) on conflict do nothing;
 perform 1 from pilot_accounts where user_id=p_user for update;
 select * into r from pilot_orders where session_id=p_session for update;
 if not found or r.user_id is distinct from p_user or r.amount is distinct from p_amount or r.currency is distinct from p_currency then raise exception 'Payment does not match order'; end if;
 if r.fulfilled then return jsonb_build_object('already_fulfilled',true); end if;
 update pilot_orders set fulfilled=true where session_id=p_session;
 update pilot_accounts set credits=credits+r.credits where user_id=p_user;
 return jsonb_build_object('already_fulfilled',false,'credits_added',r.credits);
end $$;

-- Vercel stops a check after 300 seconds. Reclaim older abandoned reservations on account refresh.
create function public.pilot_reclaim_stale(p_user uuid) returns integer
language plpgsql security definer set search_path=public as $$
declare restored integer;
begin
 perform 1 from pilot_accounts where user_id=p_user for update;
 with released as (
  update pilot_usage set status='released' where user_id=p_user and status='reserved' and created_at<now()-interval '15 minutes' returning 1
 ) select count(*) into restored from released;
 if restored>0 then update pilot_accounts set credits=credits+restored where user_id=p_user; end if;
 return restored;
end $$;

-- Privileged functions are server-only: never expose service_role keys to a browser.
revoke all on function public.pilot_reclaim_stale(uuid),public.pilot_set_inventory(uuid,jsonb,integer),public.pilot_reserve_check(uuid,uuid,text),public.pilot_release_check(uuid,uuid),public.pilot_complete_check(uuid,uuid,text,jsonb),public.pilot_fulfill_order(text,uuid,integer,text) from public, anon, authenticated;
grant execute on function public.pilot_reclaim_stale(uuid),public.pilot_set_inventory(uuid,jsonb,integer),public.pilot_reserve_check(uuid,uuid,text),public.pilot_release_check(uuid,uuid),public.pilot_complete_check(uuid,uuid,text,jsonb),public.pilot_fulfill_order(text,uuid,integer,text) to service_role;

commit;
