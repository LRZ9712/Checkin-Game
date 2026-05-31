import os
import json
import time
import random
import asyncio
import aiohttp
import re
from datetime import datetime, timedelta
from io import BytesIO

# 引入轻量级绘图库、裁剪工具和滤镜
from PIL import Image as PILImage, ImageDraw, ImageFont, ImageOps, ImageFilter

# 尝试导入表情渲染库 (仅在非并发单人场景尝试使用，以防卡死)
try:
    from pilmoji import Pilmoji
    HAS_PILMOJI = True
except ImportError:
    HAS_PILMOJI = False

from astrbot.api.all import *
from astrbot.api.event import filter
from astrbot.api.message_components import At, Plain

@register("checkin_game", "Author", "群签到与经济抢劫插件(直连控制台通关版)", "1.7.8")
class CheckinGamePlugin(Star):
    # 🔑 核心修复：正确接收 AstrBot 官方 WebUI 传入的实时 config 字典
    def __init__(self, context: Context, config: dict = None):
        super().__init__(context)
        self.plugin_dir = os.path.dirname(__file__)
        self.data_file = os.path.join(self.plugin_dir, "data.json")
        self.font_path = os.path.join(self.plugin_dir, "AlibabaPuHuiTi-2-65-Medium.ttf")
        
        self.config = config or {}
        self.users_data = self.load_data()
        self.active_robberies = {}

    def load_data(self):
        if os.path.exists(self.data_file):
            with open(self.data_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                if data and any("points" in v for v in data.values()):
                    return {"global_migrated_backup": data}
                return data
        return {}

    def save_data(self):
        with open(self.data_file, "w", encoding="utf-8") as f:
            json.dump(self.users_data, f, ensure_ascii=False, indent=2)

    def is_group_enabled(self, group_id):
        # 直接使用官方传入的字典配置
        enabled_groups = self.config.get("enabled_groups", [])
        disabled_groups = self.config.get("disabled_groups", [])
        group_id_str = str(group_id)

        # 规则1：如果白名单有内容，则绝对优先
        if enabled_groups:
            return group_id_str in enabled_groups
            
        # 规则2：如果白名单为空，但黑名单有内容，则执行黑名单模式
        if disabled_groups:
            return group_id_str not in disabled_groups
            
        # 规则3：黑白名单都为空，默认全部开启
        return True

    def get_user(self, group_id, user_id, user_name=""):
        group_id = str(group_id)
        user_id = str(user_id)
        
        if group_id not in self.users_data:
            self.users_data[group_id] = {}
            
        if user_id not in self.users_data[group_id]:
            self.users_data[group_id][user_id] = {
                "name": user_name,
                "points": 0,
                "last_checkin": "",
                "last_rob_date": "",
                "rob_days_count": 0,
                "is_red_name": False
            }
            
        if user_name:
            self.users_data[group_id][user_id]["name"] = user_name
            
        return self.users_data[group_id][user_id]

    # ================= APIs =================
    
    async def fetch_hitokoto(self):
        async with aiohttp.ClientSession() as session:
            async with session.get("https://v1.hitokoto.cn/?encode=text") as resp:
                return await resp.text() if resp.status == 200 else "我早已踏过深渊，又岂会畏惧黑夜!"

    async def fetch_image_bytes(self, url, timeout=10):
        try:
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36',
                'Referer': 'https://www.google.com/'
            }
            timeout_obj = aiohttp.ClientTimeout(total=timeout)
            async with aiohttp.ClientSession(headers=headers, timeout=timeout_obj) as session:
                async with session.get(url) as resp:
                    if resp.status == 200:
                        return await resp.read()
        except:
            return None
        return None

    async def fetch_random_bg(self):
        bg_dir = os.path.join(self.plugin_dir, "bg_images")
        if os.path.exists(bg_dir):
            valid_exts = ('.png', '.jpg', '.jpeg', '.webp')
            imgs = [f for f in os.listdir(bg_dir) if f.lower().endswith(valid_exts)]
            if imgs:
                chosen = random.choice(imgs)
                try:
                    with open(os.path.join(bg_dir, chosen), 'rb') as f:
                        return f.read()
                except:
                    pass

        apis = [
            "https://api.suyanw.cn/api/Yourname.php",
            "https://api.suyanw.cn/api/comic.php",
            "https://t.mwm.moe/pc",               
            "https://www.loliapi.com/acg/pc/"     
        ]
        fallback = "https://p1.ssl.qhimgs1.com/t02facf27f631c0e961.jpg"
        
        random.shuffle(apis)
        for api in apis:
            bytes_data = await self.fetch_image_bytes(api)
            if bytes_data:
                try:
                    PILImage.open(BytesIO(bytes_data)).verify()
                    return bytes_data
                except:
                    continue
        return await self.fetch_image_bytes(fallback)

    # ================= Pillow 绘图引擎 =================
    
    def get_font(self, size):
        try:
            return ImageFont.truetype(self.font_path, size)
        except Exception as e:
            return ImageFont.load_default()

    def make_circle_avatar(self, img_bytes, size=(100, 100)):
        try:
            if not img_bytes:
                raise ValueError("No image bytes")
            img = PILImage.open(BytesIO(img_bytes)).convert("RGBA")
            img = img.resize(size, PILImage.Resampling.LANCZOS)
            mask = PILImage.new('L', size, 0)
            draw = ImageDraw.Draw(mask)
            draw.ellipse((0, 0) + size, fill=255)
            output = PILImage.new('RGBA', size, (0, 0, 0, 0))
            output.paste(img, (0, 0), mask)
            return output
        except:
            # 防崩溃：生成纯色占位头像
            return PILImage.new('RGBA', size, color=(200, 200, 200, 255))

    def load_custom_icon(self, filename, size=(32, 32)):
        path = os.path.join(self.plugin_dir, filename)
        if os.path.exists(path):
            try:
                icon = PILImage.open(path).convert("RGBA")
                return icon.resize(size, PILImage.Resampling.LANCZOS)
            except:
                pass
        return None

    def draw_vector_like(self, draw, x, y, color):
        draw.arc([x, y, x+12, y+12], 135, 360, fill=color, width=2)
        draw.arc([x+12, y, x+24, y+12], 180, 45, fill=color, width=2)
        draw.line([x+1.5, y+10, x+12, y+22], fill=color, width=2)
        draw.line([x+12, y+22, x+22.5, y+10], fill=color, width=2)

    def draw_vector_comment(self, draw, x, y, color):
        draw.rounded_rectangle([x, y+2, x+24, y+18], radius=4, outline=color, width=2)
        draw.polygon([(x+6, y+18), (x+6, y+25), (x+12, y+18)], fill=color)

    def draw_vector_share(self, draw, x, y, color):
        draw.polygon([(x, y+10), (x+22, y), (x+12, y+22), (x+10, y+12)], outline=color, width=2)
        draw.line([x+10, y+12, x+22, y], fill=color, width=2)

    def draw_vector_bookmark(self, draw, x, y, color):
        draw.line([x, y, x+18, y], fill=color, width=2)
        draw.line([x, y, x, y+24], fill=color, width=2)
        draw.line([x+18, y, x+18, y+24], fill=color, width=2)
        draw.line([x, y+24, x+9, y+16], fill=color, width=2)
        draw.line([x+9, y+16, x+18, y+24], fill=color, width=2)

    # ================= 签到卡片生成 =================
    async def draw_checkin_image(self, user_id, name, points, quote):
        avatar_url = f"https://q4.qlogo.cn/headimg_dl?dst_uin={user_id}&spec=640"
        
        avatar_bytes, bg_bytes = await asyncio.gather(
            self.fetch_image_bytes(avatar_url, timeout=3),
            self.fetch_random_bg()
        )
        
        target_w = 620
        img_h = 450 
        main_img = None
        
        if bg_bytes:
            try:
                raw_img = PILImage.open(BytesIO(bg_bytes)).convert("RGB")
                ratio = target_w / float(raw_img.width)
                img_h = int(raw_img.height * ratio)
                if img_h > 1200: img_h = 1200
                main_img = raw_img.resize((target_w, img_h), PILImage.Resampling.LANCZOS)
            except:
                pass
                
        quote_text = f"『 {quote} 』"
        line_length = 30
        lines = [quote_text[i:i+line_length] for i in range(0, len(quote_text), line_length)]
        quote_h = len(lines) * 25
        
        bottom_area_h = 20 + 30 + 15 + 30 + 30 + quote_h + 40 + 20
        card_h = 110 + img_h + bottom_area_h
        canvas_h = card_h + 60 
        
        canvas = PILImage.new('RGB', (680, canvas_h), color=(248, 248, 248))
        
        shadow_layer = PILImage.new('RGBA', canvas.size, (0, 0, 0, 0))
        shadow_draw = ImageDraw.Draw(shadow_layer)
        shadow_draw.rounded_rectangle([(20, 30), (660, canvas_h - 30)], radius=30, fill=(0, 0, 0, 35))
        shadow_layer = shadow_layer.filter(ImageFilter.GaussianBlur(15))
        canvas.paste(shadow_layer, (0, 0), mask=shadow_layer)
        
        draw = ImageDraw.Draw(canvas)
        draw.rounded_rectangle([(20, 20), (660, canvas_h - 40)], radius=30, fill=(255, 255, 255))
        
        avatar = self.make_circle_avatar(avatar_bytes, size=(50, 50))
        canvas.paste(avatar, (40, 40), mask=avatar)
        
        font_name = self.get_font(22)
        font_icons = self.get_font(26)
        title_name = name[:15] + "..." if len(name) > 15 else name
        
        try:
            if HAS_PILMOJI:
                with Pilmoji(canvas) as pilmoji:
                    pilmoji.text((110, 52), title_name, font=font_name, fill=(38, 38, 38))
            else:
                draw.text((110, 52), title_name, font=font_name, fill=(38, 38, 38))
        except Exception:
            draw.text((110, 52), title_name, font=font_name, fill=(38, 38, 38))
            
        draw.text((610, 40), "...", font=font_icons, fill=(38, 38, 38)) 
        
        if main_img:
            canvas.paste(main_img, (30, 110))
        else:
            draw.rectangle([(30, 110), (650, 110 + img_h)], fill=(240, 240, 240))
        
        y_actions = 110 + img_h + 20
        icon_color = (60, 60, 60)
        
        icon_like = self.load_custom_icon("icon_like.png", (28, 28))
        if icon_like: canvas.paste(icon_like, (40, y_actions - 2), mask=icon_like)
        else: self.draw_vector_like(draw, 40, y_actions, icon_color)

        icon_comment = self.load_custom_icon("icon_comment.png", (28, 28))
        if icon_comment: canvas.paste(icon_comment, (85, y_actions - 2), mask=icon_comment)
        else: self.draw_vector_comment(draw, 85, y_actions, icon_color)

        icon_share = self.load_custom_icon("icon_share.png", (28, 28))
        if icon_share: canvas.paste(icon_share, (130, y_actions - 2), mask=icon_share)
        else: self.draw_vector_share(draw, 130, y_actions, icon_color)

        icon_bookmark = self.load_custom_icon("icon_bookmark.png", (28, 28))
        if icon_bookmark: canvas.paste(icon_bookmark, (590, y_actions - 2), mask=icon_bookmark)
        else: self.draw_vector_bookmark(draw, 590, y_actions, icon_color)

        current_y = y_actions + 45
        font_bold = self.get_font(20)
        font_quote = self.get_font(18)
        
        try:
            if HAS_PILMOJI:
                with Pilmoji(canvas) as pilmoji:
                    pilmoji.text((40, current_y), f"{title_name} 签到成功！", font=font_bold, fill=(38, 38, 38))
            else:
                draw.text((40, current_y), f"{title_name} 签到成功！", font=font_bold, fill=(38, 38, 38))
        except Exception:
            draw.text((40, current_y), f"{title_name} 签到成功！", font=font_bold, fill=(38, 38, 38))
            
        current_y += 30
        draw.text((40, current_y), f"财富: {points} 积分", font=font_quote, fill=(80, 80, 80))
        
        current_y += 40
        for line in lines:
            draw.text((40, current_y), line, font=font_quote, fill=(50, 50, 50))
            current_y += 25
            
        current_y += 10
        draw.text((40, current_y), datetime.now().strftime("%Y-%m-%d  %H:%M"), font=self.get_font(14), fill=(150, 150, 150))

        out_path = os.path.abspath(os.path.join(self.plugin_dir, "temp_checkin.jpg"))
        canvas.save(out_path, format='JPEG', quality=90)
        return out_path

    # ================= 资料卡片生成 =================
    async def draw_profile_image(self, user_id, name, points, quote, rob_days):
        avatar_url = f"https://q4.qlogo.cn/headimg_dl?dst_uin={user_id}&spec=640"
        avatar_bytes, bg_bytes = await asyncio.gather(
            self.fetch_image_bytes(avatar_url, timeout=3),
            self.fetch_random_bg()
        )
        
        card_w, card_h = 560, 750
        canvas_w, canvas_h = card_w + 120, card_h + 120
        canvas = PILImage.new('RGB', (canvas_w, canvas_h), color=(248, 248, 248))
        
        card_x, card_y = 60, 50 
        
        shadow_layer = PILImage.new('RGBA', canvas.size, (0, 0, 0, 0))
        shadow_draw = ImageDraw.Draw(shadow_layer)
        shadow_draw.rounded_rectangle([(card_x, card_y + 15), (card_x + card_w, card_y + card_h + 15)], radius=40, fill=(0, 0, 0, 35))
        shadow_layer = shadow_layer.filter(ImageFilter.GaussianBlur(15))
        canvas.paste(shadow_layer, (0, 0), mask=shadow_layer)

        draw = ImageDraw.Draw(canvas)
        draw.rounded_rectangle([(card_x, card_y), (card_x + card_w, card_y + card_h)], radius=40, fill=(255, 255, 255))
        
        if bg_bytes:
            try:
                bg_img = PILImage.open(BytesIO(bg_bytes)).convert("RGB")
                bg_img = ImageOps.fit(bg_img, (card_w, 240), PILImage.Resampling.LANCZOS)
                
                mask = PILImage.new('L', (card_w, 240), 0)
                mask_draw = ImageDraw.Draw(mask)
                mask_draw.rounded_rectangle([(0, 0), (card_w, 240 + 40)], radius=40, fill=255)
                
                canvas.paste(bg_img, (card_x, card_y), mask)
            except:
                draw.rounded_rectangle([(card_x, card_y), (card_x + card_w, card_y + 240)], radius=40, fill=(200, 210, 220))
        
        btn_w, btn_h = 130, 46
        btn_x, btn_y = card_x + card_w - btn_w - 20, card_y + 20
        draw.rounded_rectangle([(btn_x, btn_y), (btn_x + btn_w, btn_y + btn_h)], radius=23, fill=(250, 250, 250), outline=(200, 200, 200), width=1)
        draw.text((btn_x + 30, btn_y + 10), "Follow +", font=self.get_font(18), fill=(30, 30, 30))

        avatar = self.make_circle_avatar(avatar_bytes, size=(130, 130))
        white_bg = PILImage.new('RGBA', (142, 142), (255, 255, 255, 0))
        white_draw = ImageDraw.Draw(white_bg)
        white_draw.ellipse([(0, 0), (142, 142)], fill=(255, 255, 255, 255))
        white_bg.paste(avatar, (6, 6), mask=avatar)
        canvas.paste(white_bg, (card_x + 40, card_y + 160), mask=white_bg)

        font_name = self.get_font(36)
        title_name = name[:12] + "..." if len(name) > 12 else name
        
        try:
            if HAS_PILMOJI:
                with Pilmoji(canvas) as pilmoji:
                    pilmoji.text((card_x + 40, card_y + 320), title_name, font=font_name, fill=(30, 30, 30))
            else:
                draw.text((card_x + 40, card_y + 320), title_name, font=font_name, fill=(30, 30, 30))
        except Exception:
            draw.text((card_x + 40, card_y + 320), title_name, font=font_name, fill=(30, 30, 30))
            
        lv = (points // 10) + 1
        font_tag = self.get_font(16)
        tag_text = f"Lv.{lv} | 初入江湖" 
        tag_w = len(tag_text) * 10 + 20 
        draw.rounded_rectangle([(card_x + 40, card_y + 375), (card_x + 40 + tag_w, card_y + 405)], radius=8, fill=(230, 240, 255))
        draw.text((card_x + 50, card_y + 382), tag_text, font=font_tag, fill=(0, 120, 255))

        font_bio = self.get_font(20)
        quote_text = f"{quote}"
        line_length = 24
        lines = [quote_text[i:i+line_length] for i in range(0, len(quote_text), line_length)]
        y_bio = card_y + 420
        for line in lines[:2]: 
            draw.text((card_x + 40, y_bio), line, font=font_bio, fill=(120, 120, 120))
            y_bio += 30

        stat_y = card_y + 520
        draw.line([(card_x, stat_y), (card_x + card_w, stat_y)], fill=(240, 240, 240), width=2)
        draw.line([(card_x, stat_y + 130), (card_x + card_w, stat_y + 130)], fill=(240, 240, 240), width=2)
        
        col_w = card_w // 3
        draw.line([(card_x + col_w, stat_y + 20), (card_x + col_w, stat_y + 110)], fill=(240, 240, 240), width=2)
        draw.line([(card_x + col_w * 2, stat_y + 20), (card_x + col_w * 2, stat_y + 110)], fill=(240, 240, 240), width=2)

        font_stat_val = self.get_font(28)
        font_stat_lbl = self.get_font(18)

        draw.text((card_x + 60, stat_y + 30), f"{points}", font=font_stat_val, fill=(30, 30, 30))
        draw.text((card_x + 60, stat_y + 75), "财富 (Pts)", font=font_stat_lbl, fill=(150, 150, 150))

        draw.text((card_x + col_w + 60, stat_y + 30), f"{rob_days}", font=font_stat_val, fill=(30, 30, 30))
        draw.text((card_x + col_w + 60, stat_y + 75), "罪恶 (Crimes)", font=font_stat_lbl, fill=(150, 150, 150))

        draw.text((card_x + col_w * 2 + 60, stat_y + 30), f"Lv.{lv}", font=font_stat_val, fill=(30, 30, 30))
        draw.text((card_x + col_w * 2 + 60, stat_y + 75), "等级 (Level)", font=font_stat_lbl, fill=(150, 150, 150))

        icon_ins = self.load_custom_icon("icon_ins.png", (32, 32))
        icon_x = self.load_custom_icon("icon_x.png", (32, 32))
        icon_web = self.load_custom_icon("icon_web.png", (32, 32))
        
        icon_y = stat_y + 155
        bx1, bx2, bx3 = card_x + 140, card_x + 280, card_x + 420
        
        def draw_centered_icon(icon_img, center_x, y, fallback_text):
            if icon_img:
                canvas.paste(icon_img, (center_x - 16, y), mask=icon_img)
            else:
                draw.rounded_rectangle([center_x - 12, y + 4, center_x + 12, y + 28], radius=6, outline=(180, 180, 180), width=2)
                draw.text((center_x - 6, y + 9), fallback_text, font=self.get_font(12), fill=(180, 180, 180))

        draw_centered_icon(icon_ins, bx1, icon_y, "i")
        draw_centered_icon(icon_x, bx2, icon_y, "X")
        draw_centered_icon(icon_web, bx3, icon_y, "W")

        out_path = os.path.abspath(os.path.join(self.plugin_dir, f"temp_profile_{user_id}.jpg"))
        canvas.save(out_path, format='JPEG', quality=90)
        return out_path

    # ================= 排行榜生成 =================
    async def draw_leaderboard_image(self, top_users, group_id):
        row_height = 80
        total_height = 120 + (len(top_users) * row_height) + 100
        
        canvas = PILImage.new('RGB', (500, max(total_height, 200)), color=(239, 233, 217))
        draw = ImageDraw.Draw(canvas)
        
        font_title = self.get_font(30)
        font_name = self.get_font(20)
        font_score = self.get_font(18)
        font_badge = self.get_font(14)
        
        draw.text((160, 30), "- 财富排行榜 -", font=font_title, fill=(92, 84, 70))
        
        # 极速断路器：只等2秒，绝不让拉取头像卡死整个排行榜
        avatar_tasks = [self.fetch_image_bytes(f"https://q4.qlogo.cn/headimg_dl?dst_uin={uid}&spec=640", timeout=2) for uid, _ in top_users]
        avatar_bytes_list = await asyncio.gather(*avatar_tasks)
        
        y_offset = 100
        for idx, ((uid, data), avatar_bytes) in enumerate(zip(top_users, avatar_bytes_list)):
            draw.rounded_rectangle([(20, y_offset), (480, y_offset + 65)], radius=10, fill=(248, 245, 238))
            
            rank_str = str(idx + 1)
            draw.text((40, y_offset + 20), rank_str, font=font_title, fill=(191, 165, 136))
            
            avatar = self.make_circle_avatar(avatar_bytes, size=(50, 50))
            canvas.paste(avatar, (90, y_offset + 7), mask=avatar)
                
            display_name = data.get("name") if data.get("name") else str(uid)
            display_name = display_name[:15] + "..." if len(display_name) > 15 else display_name
            
            # 🛡️ 核心防崩溃机制：排行榜强制放弃复杂的 Emoji 联网下载渲染，强行使用本地字体极速绘制
            draw.text((160, y_offset + 12), display_name, font=font_name, fill=(74, 68, 58))
                
            draw.text((160, y_offset + 40), f"{data['points']} 积分", font=font_score, fill=(140, 130, 113))
            
            if data.get("is_red_name"):
                draw.rounded_rectangle([(390, y_offset + 20), (460, y_offset + 45)], radius=5, fill=(255, 94, 94))
                draw.text((405, y_offset + 24), "通缉犯", font=font_badge, fill=(255, 255, 255))
            
            y_offset += row_height

        font_footer = self.get_font(18)
        footer_color = (140, 130, 113)
        
        draw.line([(40, y_offset + 10), (460, y_offset + 10)], fill=(220, 210, 190), width=2)
        draw.text((40, y_offset + 25), "10积分   可兑换潇潇和你的设定关系", font=font_footer, fill=footer_color)
        draw.text((40, y_offset + 55), "20积分   拉潇潇一次", font=font_footer, fill=footer_color)

        out_path = os.path.abspath(os.path.join(self.plugin_dir, f"temp_leaderboard_{group_id}.jpg"))
        canvas.save(out_path, format='JPEG', quality=90)
        return out_path

    # ================= 指令监听 =================

    @filter.event_message_type(filter.EventMessageType.ALL)
    async def checkin(self, event: AstrMessageEvent):
        msg_text = event.message_obj.message_str.strip()
        if msg_text not in ["签到", "/签到"]:
            return

        group_id = str(event.message_obj.group_id) if event.message_obj.group_id else "private"
        if not self.is_group_enabled(group_id):
            return

        user_id = event.get_sender_id()
        user_name = event.get_sender_name()
        user_data = self.get_user(group_id, user_id, user_name)
        
        today = datetime.now().strftime("%Y-%m-%d")
        if user_data["last_checkin"] == today:
            yield event.plain_result("今天已经签过到了哦！")
            return
            
        user_data["points"] += 1
        user_data["last_checkin"] = today
        self.save_data()
        
        quote = await self.fetch_hitokoto()
        
        img_path = await self.draw_checkin_image(user_id, user_name, user_data["points"], quote)
        yield event.image_result(str(img_path))

    @filter.command("我的积分")
    async def my_points(self, event: AstrMessageEvent):
        group_id = str(event.message_obj.group_id) if event.message_obj.group_id else "private"
        if not self.is_group_enabled(group_id):
            return
            
        user_id = event.get_sender_id()
        user_name = event.get_sender_name()
        user_data = self.get_user(group_id, user_id, user_name)
        
        quote = await self.fetch_hitokoto()
        rob_days = user_data.get("rob_days_count", 0)
        
        img_path = await self.draw_profile_image(user_id, user_name, user_data["points"], quote, rob_days)
        
        yield event.image_result(str(img_path))

    @filter.command("抢劫")
    async def rob(self, event: AstrMessageEvent):
        group_id = str(event.message_obj.group_id)
        if not group_id or group_id == "None":
            yield event.plain_result("抢劫只能在群聊中进行！")
            return

        if not self.is_group_enabled(group_id):
            return

        robber_id = event.get_sender_id()
        robber_name = event.get_sender_name()
        
        target_id = None
        for comp in event.message_obj.message:
            if isinstance(comp, At):
                target_id = str(comp.qq)
                break
                
        if not target_id:
            yield event.plain_result("你要抢劫谁？请 @ 目标！")
            return
            
        if target_id == robber_id:
            yield event.plain_result("你不能抢劫自己！")
            return

        robber_data = self.get_user(group_id, robber_id, robber_name)
        target_data = self.get_user(group_id, target_id)
        
        if target_data["points"] <= 0:
            yield event.plain_result("他已经一无所有了，光脚的不怕穿鞋的，放过他吧！")
            return

        today_str = datetime.now().strftime("%Y-%m-%d")
        if robber_data["last_rob_date"] == today_str:
            yield event.plain_result("你今天已经作案过了，明天再来吧！")
            return

        if group_id in self.active_robberies:
            yield event.plain_result("本群正有抢劫案发生，请稍后再试或前去 /行侠仗义！")
            return

        last_date_obj = datetime.strptime(robber_data["last_rob_date"], "%Y-%m-%d").date() if robber_data["last_rob_date"] else None
        today_obj = datetime.now().date()
        
        if last_date_obj and today_obj == last_date_obj + timedelta(days=1):
            robber_data["rob_days_count"] += 1
        else:
            robber_data["rob_days_count"] = 1
            
        if robber_data["rob_days_count"] >= 5:
            robber_data["is_red_name"] = True
            
        robber_data["last_rob_date"] = today_str
        self.save_data()

        if random.random() < self.config.get("rob_fail_rate", 0.4):
            yield event.plain_result(f"【抢劫失败】{robber_name} 试图抢劫，但脚底打滑摔了一跤！")
            return
            
        raw_steal = random.randint(self.config.get("rob_min_points", 1), self.config.get("rob_max_points", 8))
        steal_points = min(raw_steal, target_data["points"])

        if raw_steal > steal_points:
            msg = f"⚠️ 警告！【{robber_name}】发起了抢劫！但目标太穷了，把兜翻底朝天也只有 {steal_points} 积分！\n⏳ 3 分钟内，输入 /行侠仗义 可阻止这场劫案！"
        else:
            msg = f"⚠️ 警告！【{robber_name}】正在抢劫目标！涉及积分：{steal_points}\n⏳ 3 分钟内，输入 /行侠仗义 可阻止这场劫案！"

        yield event.plain_result(msg)

        task = asyncio.create_task(self.robbery_timeout(group_id, robber_id, target_id, steal_points))
        self.active_robberies[group_id] = {
            "robber_id": robber_id,
            "target_id": target_id,
            "points": steal_points,
            "task": task,
            "timestamp": time.time()
        }

    async def robbery_timeout(self, group_id, robber_id, target_id, points):
        await asyncio.sleep(180)
        
        if group_id in self.active_robberies:
            target_data = self.users_data[group_id][target_id]
            robber_data = self.users_data[group_id][robber_id]
            
            actual_steal = min(points, target_data["points"])
            robber_data["points"] += actual_steal
            target_data["points"] = max(0, target_data["points"] - actual_steal)
            
            self.save_data()
            del self.active_robberies[group_id]

    @filter.command("行侠仗义")
    async def intervene(self, event: AstrMessageEvent):
        group_id = str(event.message_obj.group_id)
        if not self.is_group_enabled(group_id):
            return

        hero_id = event.get_sender_id()
        hero_name = event.get_sender_name()

        if group_id not in self.active_robberies:
            yield event.plain_result("当前没有发生抢劫案，已经被抢完啦，你来晚了！")
            return

        rob_data = self.active_robberies[group_id]
        
        if hero_id == rob_data["robber_id"]:
            yield event.plain_result("贼喊捉贼是吧？")
            return
            
        if hero_id == rob_data["target_id"]:
            yield event.plain_result("你都被五花大绑了，还想自己救自己？老实等别人来救吧！")
            return

        robber_data = self.get_user(group_id, rob_data["robber_id"])
        hero_user_data = self.get_user(group_id, hero_id, hero_name)
        
        if random.random() < self.config.get("intervene_fail_rate", 0.4):
            target_data = self.get_user(group_id, rob_data["target_id"])
            
            actual_steal = min(rob_data["points"], target_data["points"])
            robber_data["points"] += actual_steal
            target_data["points"] = max(0, target_data["points"] - actual_steal)
            
            hero_loss = random.randint(self.config.get("rob_min_points", 1), self.config.get("rob_max_points", 8))
            actual_hero_loss = min(hero_loss, hero_user_data["points"])
            
            robber_data["points"] += actual_hero_loss
            hero_user_data["points"] = max(0, hero_user_data["points"] - actual_hero_loss)
            
            rob_data["task"].cancel()
            del self.active_robberies[group_id]
            self.save_data()
            
            fail_msg = f"💥 哎呀！大侠 {hero_name} 技不如人被揍趴下了！\n劫案继续，受害者被抢走 {actual_steal} 积分。\n"
            if actual_hero_loss < hero_loss:
                fail_msg += f"大侠也被顺手牵羊，搜刮走了身上仅有的 {actual_hero_loss} 积分！"
            else:
                fail_msg += f"大侠连自己都没保住，也被顺手牵羊抢走了 {actual_hero_loss} 积分！"
                
            yield event.plain_result(fail_msg)
            return
            
        else:
            rob_data["task"].cancel()
            del self.active_robberies[group_id]
            
            if robber_data["is_red_name"]:
                penalty = self.config.get("intervene_penalty_red_name", 10)
                tag = "【红名通缉犯】"
            else:
                penalty = self.config.get("intervene_penalty_normal", 5)
                tag = "【普通劫匪】"
                
            robber_data["points"] = max(0, robber_data["points"] - penalty)
            hero_reward = self.config.get("hero_reward_points", 3)
            hero_user_data["points"] += hero_reward
            self.save_data()
            
            yield event.plain_result(
                f"🗡️ 大侠 {hero_name} 出手相助！受害者完好无损。\n"
                f"抓获 {tag} 一名，扣除其 {penalty} 积分。\n"
                f"大侠获得 {hero_reward} 积分系统奖励！"
            )

    @filter.command("排行榜")
    async def leaderboard(self, event: AstrMessageEvent):
        group_id = str(event.message_obj.group_id) if event.message_obj.group_id else "private"
        if not self.is_group_enabled(group_id):
            return

        group_users = self.users_data.get(group_id, {})
        sorted_users = sorted(group_users.items(), key=lambda x: x[1]["points"], reverse=True)
        top_users = sorted_users[:10]
        
        if not top_users:
            yield event.plain_result("本群暂无排行榜数据！大家快来签到吧~")
            return

        img_path = await self.draw_leaderboard_image(top_users, group_id)
        yield event.image_result(str(img_path))

    @filter.command("财富加")
    async def add_points(self, event: AstrMessageEvent):
        group_id = str(event.message_obj.group_id)
        if not group_id or group_id == "None":
            yield event.plain_result("此指令只能在群聊中使用！")
            return
            
        if not self.is_group_enabled(group_id):
            return

        sender_id = str(event.get_sender_id())
        
        if sender_id not in self.config.get("admin_qq", []):
            yield event.plain_result("🚫 权限不足！只有系统管理员可以修改积分。")
            return
            
        target_id = None
        for comp in event.message_obj.message:
            if isinstance(comp, At):
                target_id = str(comp.qq)
                break
                
        if not target_id:
            yield event.plain_result("请 @ 你要增加积分的群友！\n用法：/财富加 @目标 30")
            return

        amount = 0
        for comp in event.message_obj.message:
            if isinstance(comp, Plain):
                nums = re.findall(r'\d+', comp.text)
                if nums:
                    amount = int(nums[0])
                    break
                    
        if amount <= 0:
            yield event.plain_result("格式错误，请输入有效的数字。\n用法：/财富加 @目标 30")
            return
            
        target_data = self.get_user(group_id, target_id)
        target_data["points"] += amount
        self.save_data()
        
        yield event.plain_result(f"✅ 操作成功！\n已为该用户增加 {amount} 积分。\n当前总余额：{target_data['points']} 积分。")

    @filter.command("财富减")
    async def sub_points(self, event: AstrMessageEvent):
        group_id = str(event.message_obj.group_id)
        if not group_id or group_id == "None":
            yield event.plain_result("此指令只能在群聊中使用！")
            return
            
        if not self.is_group_enabled(group_id):
            return

        sender_id = str(event.get_sender_id())
        
        if sender_id not in self.config.get("admin_qq", []):
            yield event.plain_result("🚫 权限不足！只有系统管理员可以修改积分。")
            return
            
        target_id = None
        for comp in event.message_obj.message:
            if isinstance(comp, At):
                target_id = str(comp.qq)
                break
                
        if not target_id:
            yield event.plain_result("请 @ 你要扣除积分的群友！\n用法：/财富减 @目标 30")
            return

        amount = 0
        for comp in event.message_obj.message:
            if isinstance(comp, Plain):
                nums = re.findall(r'\d+', comp.text)
                if nums:
                    amount = int(nums[0])
                    break
                    
        if amount <= 0:
            yield event.plain_result("格式错误，请输入有效的数字。\n用法：/财富减 @目标 30")
            return
            
        target_data = self.get_user(group_id, target_id)
        target_data["points"] = max(0, target_data["points"] - amount)
        self.save_data()
        
        yield event.plain_result(f"✅ 操作成功！\n已扣除该用户 {amount} 积分。\n当前总余额：{target_data['points']} 积分。")
