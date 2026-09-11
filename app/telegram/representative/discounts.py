from __future__ import annotations
from datetime import datetime
from telethon import Button, events
from app.runtime.context import get_tenant
from app.runtime.dispatcher import tenant_dispatch
from app.services.discounts import SERVICE
from app.services.representative_dashboard import RepresentativeDashboardService
PREFIX=b"rep:discounts:"; BACK=b"rep:rep.home"; DASH=RepresentativeDashboardService(); STATES={}
def register(client,tenant_id=None):
 async def cb(e):
  async with tenant_dispatch(tenant_id): await callback(e)
 async def msg(e):
  async with tenant_dispatch(tenant_id): await message(e)
 client.add_event_handler(cb,events.CallbackQuery(func=lambda e: bool(e.data and e.data.startswith(PREFIX)))); client.add_event_handler(msg,events.NewMessage(incoming=True))
async def owner(e): return bool(e.is_private and get_tenant() and await DASH.is_owner(e.sender_id))
def label(d): return f"{'🟢' if d.enabled else '🔴'} {d.code} — {d.percent:g}%"
async def render():
 items=await SERVICE.list(); text="🎟 **تخفیف‌ها**\n\n"+(("هنوز کد تخفیفی ساخته نشده است.") if not items else "\n".join(f"• {label(x)} | استفاده: {x.used_count}/{x.max_uses if x.max_uses else '∞'}" for x in items)); rows=[[Button.inline("➕ ساخت کد تخفیف",PREFIX+b"add")]]; rows += [[Button.inline(label(x),PREFIX+f"view:{x.id}".encode()),Button.inline("🔄",PREFIX+f"toggle:{x.id}".encode())] for x in items]; rows.append([Button.inline("🔙 داشبورد",BACK)]); return text,rows
async def callback(e):
 if not await owner(e): return await e.answer("دسترسی ندارید.",alert=True)
 a=e.data[len(PREFIX):].decode(); key=(get_tenant(),e.sender_id)
 if a in ('','list'):
  t,b=await render(); await e.edit(t,buttons=b); return await e.answer()
 if a=='add': STATES[key]={'step':'code'}; await e.edit("➕ **ساخت کد تخفیف**\n\nکد را ارسال کنید.\nمثال: `WELCOME10`",buttons=[[Button.inline("❌ لغو",PREFIX+b"cancel")]]); return await e.answer()
 if a=='cancel': STATES.pop(key,None); t,b=await render(); await e.edit(t,buttons=b); return await e.answer()
 if a.startswith('view:'):
  d=await SERVICE.get(int(a.split(':')[1]));
  if not d:return await e.answer("کد پیدا نشد.",alert=True)
  exp=d.expires_at.strftime('%Y-%m-%d %H:%M') if d.expires_at else 'بدون انقضا'; t=f"🎟 **{d.code}**\n\n📉 تخفیف: **{d.percent:g}%**\n🔢 استفاده: **{d.used_count}/{d.max_uses if d.max_uses else '∞'}**\n⏳ انقضا: **{exp}**\n📌 وضعیت: **{'فعال' if d.enabled else 'غیرفعال'}**"; b=[[Button.inline("🔄 تغییر وضعیت",PREFIX+f"toggle:{d.id}".encode())],[Button.inline("🗑 حذف",PREFIX+f"delete_confirm:{d.id}".encode())],[Button.inline("🔙 لیست",PREFIX+b"list")]]; await e.edit(t,buttons=b); return await e.answer()
 if a.startswith('toggle:'): await SERVICE.toggle(int(a.split(':')[1])); t,b=await render(); await e.edit(t,buttons=b); return await e.answer("وضعیت تغییر کرد.")
 if a.startswith('delete_confirm:'):
  i=int(a.split(':')[1]); d=await SERVICE.get(i)
  if not d:return await e.answer("کد پیدا نشد.",alert=True)
  await e.edit(f"⚠️ حذف **{d.code}** قطعی است؟",buttons=[[Button.inline("✅ حذف",PREFIX+f"delete:{i}".encode())],[Button.inline("❌ انصراف",PREFIX+f"view:{i}".encode())]]); return await e.answer()
 if a.startswith('delete:'): await SERVICE.delete(int(a.split(':')[1])); t,b=await render(); await e.edit(t,buttons=b); return await e.answer("حذف شد.")
 await e.answer("گزینه نامعتبر است.",alert=True)
async def message(e):
 if not await owner(e): return
 key=(get_tenant(),e.sender_id); s=STATES.get(key)
 if not s:return
 text=(e.raw_text or '').strip()
 if text in {'لغو','/cancel','❌'}: STATES.pop(key,None); await e.respond("❌ عملیات لغو شد."); return
 try:
  if s['step']=='code':
   if not 3<=len(text)<=64:raise ValueError('کد باید بین 3 تا 64 کاراکتر باشد.')
   s.update(code=text,step='percent'); await e.respond('📉 درصد تخفیف را وارد کنید. مثال: `10`'); return
  if s['step']=='percent':
   p=float(text.replace('%',''))
   if not 0<p<=100:raise ValueError('درصد باید بین 1 تا 100 باشد.')
   s.update(percent=p,step='max_uses'); await e.respond('🔢 سقف استفاده را وارد کنید یا `0` برای نامحدود.'); return
  if s['step']=='max_uses':
   n=int(text)
   if n<0:raise ValueError('مقدار نامعتبر است.')
   s.update(max_uses=None if n==0 else n,step='expires'); await e.respond('⏳ تاریخ انقضا را با فرمت `YYYY-MM-DD HH:MM` وارد کنید یا `0` برای بدون انقضا.'); return
  if s['step']=='expires':
   exp=None if text=='0' else datetime.strptime(text,'%Y-%m-%d %H:%M'); d=await SERVICE.create(s['code'],s['percent'],s['max_uses'],exp); STATES.pop(key,None); await e.respond(f'✅ کد **{d.code}** ساخته شد.',buttons=[[Button.inline('🎟 تخفیف‌ها',PREFIX+b'list')]]); return
 except (ValueError,TypeError) as ex: await e.respond(f'❌ ورودی نامعتبر: {ex}\n\nدوباره تلاش کنید یا `لغو` بفرستید.')
