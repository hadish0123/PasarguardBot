from __future__ import annotations
from telethon import Button,events
from app.runtime.context import get_tenant
from app.runtime.dispatcher import tenant_dispatch
from app.services.plans import PlanService
from app.services.representative_users import SERVICE as USER_SERVICE
from app.services.texts import SERVICE as TEXT_SERVICE
PREFIX=b"user:"
async def register_handler(event,tenant_id):
 async with tenant_dispatch(tenant_id):
  if not event.is_private or not get_tenant(): return
  u=await USER_SERVICE.get_by_telegram_id(event.sender_id)
  if not u or u.blocked:return await event.answer("دسترسی ندارید.",alert=True)
  a=event.data[len(PREFIX):].decode(errors="ignore")
  if a=="home":return await event.edit(await TEXT_SERVICE.get("shop_title")+"\n\n"+await TEXT_SERVICE.get("shop_hint"),buttons=await customer_menu())
  if a=="buy":
   plans=[p for p in await PlanService().list() if p.enabled]
   if not plans:return await event.edit(await TEXT_SERVICE.get("buy_title")+"\n\n"+await TEXT_SERVICE.get("plans_empty"),buttons=[[Button.inline("🔙 فروشگاه",b"user:home")]])
   rows=[[Button.inline(f"📦 {p.name} | {p.volume_gb:g}GB / {p.days}روز | {p.price:g}",b"user:order:"+str(p.id).encode())] for p in plans];rows.append([Button.inline("🔙 فروشگاه",b"user:home")]);return await event.edit(await TEXT_SERVICE.get("buy_title")+"\n\n"+await TEXT_SERVICE.get("buy_hint"),buttons=rows)
  if a=="services":
   from app.telegram.representative.user_services import render_user
   t,b=await render_user(event.sender_id);return await event.edit(t,buttons=b)
  if a=="wallet":
   from app.telegram.representative.wallet import render_wallet
   t,b=await render_wallet(event.sender_id);return await event.edit(t,buttons=b)
  if a=="profile":
   from app.telegram.representative.profile import render_profile
   t,b=await render_profile(event.sender_id);return await event.edit(t,buttons=b)
  if a=="discount":
   from app.telegram.representative.discount_user import render
   return await render(event)
  if a=="trial":
   from app.telegram.representative.trial import render
   return await render(event)
  if a=="referral":
   from app.telegram.representative.referral import render
   t,b=await render(event.sender_id);return await event.edit(t,buttons=b)
  if a=="support":
   from app.telegram.representative.support import render
   t,b=await render(event.sender_id);return await event.edit(t,buttons=b)
async def customer_menu():
 v=await TEXT_SERVICE.all();return [[Button.inline(v["buy_button"],b"user:buy")],[Button.inline(v["services_button"],b"user:services"),Button.inline(v["wallet_button"],b"user:wallet")],[Button.inline(v["profile_button"],b"user:profile"),Button.inline(v["referral_button"],b"user:referral")],[Button.inline(v["discount_button"],b"user:discount"),Button.inline(v["trial_button"],b"user:trial")],[Button.inline(v["support_button"],b"user:support")]]
def register(client,tenant_id):
 client.add_event_handler(lambda e:register_handler(e,tenant_id),events.CallbackQuery(func=lambda e: bool(e.data and e.data.startswith(PREFIX))))
