import io
import random
import zipfile
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from functools import lru_cache
from typing import Annotated, Optional
from urllib.parse import quote

from fastapi import Cookie, Depends, FastAPI, Form, HTTPException, Request, Response, status
from fastapi.responses import HTMLResponse, RedirectResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from jose import JWTError, jwt
from PIL import Image, ImageDraw, ImageFont
from zoneinfo import ZoneInfo

# ─── App setup ───────────────────────────────────────────────────────────────

app = FastAPI()
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

SECRET_KEY = "change-me-before-deploy-use-openssl-rand-hex-32"
ALGORITHM  = "HS256"
TOKEN_EXPIRE_HOURS = 8
USERS = {"admin": "1234"}

def create_token(username: str) -> str:
    expire = datetime.now(timezone.utc) + timedelta(hours=TOKEN_EXPIRE_HOURS)
    return jwt.encode({"sub": username, "exp": expire}, SECRET_KEY, algorithm=ALGORITHM)

def get_current_user(token: Optional[str] = Cookie(default=None, alias="access_token")) -> str:
    if not token:
        raise HTTPException(status_code=status.HTTP_307_TEMPORARY_REDIRECT, headers={"Location": "/login"})
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload["sub"]
    except JWTError:
        raise HTTPException(status_code=status.HTTP_307_TEMPORARY_REDIRECT, headers={"Location": "/login"})

CurrentUser = Annotated[str, Depends(get_current_user)]

# ─── Image/font cache ────────────────────────────────────────────────────────

@lru_cache(maxsize=1)
def _load_bg_vip() -> Image.Image:
    return Image.open("static/B1N.jpg").convert("RGBA")

@lru_cache(maxsize=1)
def _load_bg_normal() -> Image.Image:
    return Image.open("static/B2.jpg").convert("RGBA")

@lru_cache(maxsize=8)
def _load_font(size: int) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype("static/SURATANADEMO-ExtraBold.ttf", size)

def _get_auto_font(draw: ImageDraw.ImageDraw, text: str, max_width: int,
                   start: int = 30, min_size: int = 20) -> ImageFont.FreeTypeFont:
    for size in range(start, min_size - 1, -1):
        font = _load_font(size)
        w = draw.textbbox((0, 0), text, font=font)[2]
        if w <= max_width:
            return font
    return _load_font(min_size)

def _bold_text(draw: ImageDraw.ImageDraw, xy: tuple[int, int], text: str,
               font: ImageFont.FreeTypeFont, fill: str = "#ffca08", boldness: int = 1) -> None:
    x, y = xy
    for dx in range(-boldness, boldness + 1):
        for dy in range(-boldness, boldness + 1):
            draw.text((x + dx, y + dy), text, font=font, fill=fill)

# ─── ระบบที่ 1: หวย VIP (ใบ B1) ────────────────────────────────────────────────
def create_image_vip(
    lottery_type: str, v_main1: Optional[str] = None, v_main2: Optional[str] = None,
    v_pair1: Optional[str] = None, v_pair2: Optional[str] = None, v_pair3: Optional[str] = None,
    v_pair4: Optional[str] = None, v_pair5: Optional[str] = None, v_pair6: Optional[str] = None,
    triple1: Optional[str] = None, triple2: Optional[str] = None, triple3: Optional[str] = None
) -> bytes:
    image = deepcopy(_load_bg_vip()).convert("RGB")
    draw  = ImageDraw.Draw(image)
    color_red = "#8b0000" 
    color_title = "#001f3f" 

    def draw_center_x(y, text, font, fill):
        bbox = draw.textbbox((0, 0), text, font=font)
        w = bbox[2] - bbox[0]
        _bold_text(draw, ((image.width - w) // 2, y), text, font, fill=fill)
        
    def draw_at_x_y(x_center, y, text, font, fill):
        bbox = draw.textbbox((0, 0), text, font=font)
        w = bbox[2] - bbox[0]
        _bold_text(draw, (x_center - (w // 2), y), text, font, fill=fill)

    font_title = _get_auto_font(draw, lottery_type, 600, start=65) 
    bbox_name = draw.textbbox((0, 0), lottery_type, font=font_title)
    draw_center_x(105 + (60 - (bbox_name[3] - bbox_name[1])) // 2, lottery_type, font_title, color_title)

    m1 = int(v_main1) if v_main1 and v_main1.isdigit() else None
    m2 = int(v_main2) if v_main2 and v_main2.isdigit() else None

    if m1 is not None and m2 is not None:
        num1, num2 = m1, m2
        if num1 == num2: num2 = random.choice([i for i in range(10) if i != num1])
    elif m1 is not None:
        num1 = m1
        num2 = random.choice([i for i in range(10) if i != num1])
    elif m2 is not None:
        num2 = m2
        num1 = random.choice([i for i in range(10) if i != num2])
    else:
        num1, num2 = random.sample(range(10), 2)

    def get_or_random_pair(user_input, default_format):
        return user_input if user_input and len(user_input) == 2 and user_input.isdigit() else default_format

    avail1 = random.sample([d for d in range(10) if d != num1], 3)
    p1 = [get_or_random_pair(v_pair1, f"{num1}{avail1[0]}"), get_or_random_pair(v_pair2, f"{num1}{avail1[1]}"), get_or_random_pair(v_pair3, f"{num1}{avail1[2]}")]
    avail2 = random.sample([d for d in range(10) if d != num2], 3)
    p2 = [get_or_random_pair(v_pair4, f"{num2}{avail2[0]}"), get_or_random_pair(v_pair5, f"{num2}{avail2[1]}"), get_or_random_pair(v_pair6, f"{num2}{avail2[2]}")]

    def get_or_random_triple(user_input, default_format):
        return user_input if user_input and len(user_input) == 3 and user_input.isdigit() else default_format

    t1_avail = random.sample([d for d in range(10) if d != num1], 2); t1_list = [num1, t1_avail[0], t1_avail[1]]; random.shuffle(t1_list)
    t2_avail = random.sample([d for d in range(10) if d != num2], 2); t2_list = [num2, t2_avail[0], t2_avail[1]]; random.shuffle(t2_list)
    t3_avail = random.sample([d for d in range(10) if d != num1], 2); t3_list = [num1, t3_avail[0], t3_avail[1]]; random.shuffle(t3_list)
    
    t1_val = get_or_random_triple(triple1, "".join(map(str, t1_list)))
    t2_val = get_or_random_triple(triple2, "".join(map(str, t2_list)))
    t3_val = get_or_random_triple(triple3, "".join(map(str, t3_list)))

    f_text = _load_font(65); f_num = _load_font(70); f_main = _load_font(85)
    
    draw_center_x(265, f"รูด    {num1} - {num2}", f_text, color_red)
    draw_center_x(375, f"เม็ดเดียว  {num1}{num2}", f_main, color_title)

    draw_at_x_y(340, 525, p1[0], f_num, color_red); draw_at_x_y(540, 525, p1[1], f_num, color_red); draw_at_x_y(740, 525, p1[2], f_num, color_red)
    draw_at_x_y(340, 625, p2[0], f_num, color_red); draw_at_x_y(540, 625, p2[1], f_num, color_red); draw_at_x_y(740, 625, p2[2], f_num, color_red)
    draw_at_x_y(300, 755, t1_val, f_num, color_red); draw_at_x_y(540, 755, t2_val, f_num, color_red); draw_at_x_y(780, 755, t3_val, f_num, color_red)

    buf = io.BytesIO()
    image.save(buf, format="JPEG", quality=85, optimize=True)
    buf.seek(0)
    return buf.read()

# ─── ระบบที่ 2: หวยปกติ (ใบ B2) ────────────────────────────────────────────────
def create_image_normal(
    lottery_type: str, n_main1: Optional[str] = None, 
    n_pair1: Optional[str] = None, n_pair2: Optional[str] = None, n_pair3: Optional[str] = None,
    n_pair4: Optional[str] = None, n_pair5: Optional[str] = None, n_pair6: Optional[str] = None,
    fournum: Optional[str] = None
) -> bytes:
    image = deepcopy(_load_bg_normal()).convert("RGB")
    draw  = ImageDraw.Draw(image)
    color_gold = "#ffca08"; color_white = "#ffffff"
    
    def draw_center_x(y, text, font, fill, stroke_w=5):
        bbox = draw.textbbox((0, 0), text, font=font)
        draw.text(((image.width - (bbox[2] - bbox[0])) // 2, y), text, font=font, fill=fill, stroke_width=stroke_w, stroke_fill="#000000")
        
    def draw_at_x_y(x_center, y, text, font, fill, stroke_w=5):
        bbox = draw.textbbox((0, 0), text, font=font)
        draw.text((x_center - ((bbox[2] - bbox[0]) // 2), y), text, font=font, fill=fill, stroke_width=stroke_w, stroke_fill="#000000")

    font_title = _get_auto_font(draw, lottery_type, 700, start=100) 
    draw_center_x(120, lottery_type, font_title, color_gold)

    thai_year = str(datetime.now(ZoneInfo("Asia/Bangkok")).year + 543)[-2:]
    date_text = datetime.now(ZoneInfo("Asia/Bangkok")).strftime(f"%-d/%-m/{thai_year}")
    draw_center_x(260, date_text, _load_font(65), color_white)

    num1 = int(n_main1) if n_main1 and n_main1.isdigit() else random.choice(range(10))
    draw_center_x(380, f"ฟัน {num1}", _load_font(90), color_white, stroke_w=6)

    def get_or_random_pair(user_input, default_format):
        return user_input if user_input and len(user_input) == 2 and user_input.isdigit() else default_format

    avail = random.sample([d for d in range(10) if d != num1], 6)
    p = [
        get_or_random_pair(n_pair1, f"{num1}{avail[0]}"), get_or_random_pair(n_pair2, f"{num1}{avail[1]}"), get_or_random_pair(n_pair3, f"{num1}{avail[2]}"),
        get_or_random_pair(n_pair4, f"{num1}{avail[3]}"), get_or_random_pair(n_pair5, f"{num1}{avail[4]}"), get_or_random_pair(n_pair6, f"{num1}{avail[5]}")
    ]

    f_pairs = _load_font(85)
    draw_at_x_y(440, 540, p[0], f_pairs, color_white); draw_at_x_y(640, 540, p[1], f_pairs, color_white); draw_at_x_y(840, 540, p[2], f_pairs, color_white)
    draw_at_x_y(440, 690, p[3], f_pairs, color_white); draw_at_x_y(640, 690, p[4], f_pairs, color_white); draw_at_x_y(840, 690, p[5], f_pairs, color_white)

    fournum_val = fournum if fournum and len(fournum) == 4 and fournum.isdigit() else f"{p[0]}{p[1]}"
    draw_center_x(860, fournum_val, _load_font(100), color_white, stroke_w=7)

    buf = io.BytesIO()
    image.save(buf, format="JPEG", quality=85, optimize=True)
    buf.seek(0)
    return buf.read()


# ─── Routes ──────────────────────────────────────────────────────────────────
@app.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    return templates.TemplateResponse("login.html", {"request": request})

@app.post("/login")
async def login(request: Request, username: str = Form(...), password: str = Form(...)):
    if USERS.get(username) != password:
        return templates.TemplateResponse("login.html", {"request": request, "error": "ชื่อผู้ใช้หรือรหัสผ่านไม่ถูกต้อง"}, status_code=400)
    response = RedirectResponse(url="/", status_code=status.HTTP_303_SEE_OTHER)
    response.set_cookie(key="access_token", value=create_token(username), httponly=True, samesite="lax", max_age=TOKEN_EXPIRE_HOURS * 3600)
    return response

@app.get("/logout")
async def logout():
    response = RedirectResponse(url="/login", status_code=status.HTTP_303_SEE_OTHER)
    response.delete_cookie("access_token")
    return response

@app.get("/", response_class=HTMLResponse)
async def lottery_page(request: Request, user: CurrentUser):
    return templates.TemplateResponse("index.html", {"request": request, "user": user})

@app.post("/")
async def lottery_generate(
    user: CurrentUser,
    lottery_type: list[str] = Form(...),
    # VIP Inputs
    v_main1: Optional[str] = Form(None), v_main2: Optional[str] = Form(None),
    v_pair1: Optional[str] = Form(None), v_pair2: Optional[str] = Form(None), v_pair3: Optional[str] = Form(None),
    v_pair4: Optional[str] = Form(None), v_pair5: Optional[str] = Form(None), v_pair6: Optional[str] = Form(None), 
    triple1: Optional[str] = Form(None), triple2: Optional[str] = Form(None), triple3: Optional[str] = Form(None), 
    # Normal Inputs
    n_main1: Optional[str] = Form(None), 
    n_pair1: Optional[str] = Form(None), n_pair2: Optional[str] = Form(None), n_pair3: Optional[str] = Form(None), 
    n_pair4: Optional[str] = Form(None), n_pair5: Optional[str] = Form(None), n_pair6: Optional[str] = Form(None), 
    fournum: Optional[str] = Form(None), 
):
    if not lottery_type:
        raise HTTPException(status_code=400, detail="กรุณาเลือกประเภทหวยอย่างน้อย 1 รายการ")

    parsed_items = []
    for lt_data in lottery_type:
        time_str, name_str = lt_data.split("|", 1) if "|" in lt_data else ("", lt_data)
        parsed_items.append({"time": time_str, "name": name_str})
    
    parsed_items.sort(key=lambda x: x["time"] if x["time"] else "99:99")

    # ฟังก์ชันช่วยเลือกวาดตามเงื่อนไขที่กำหนด
    def generate_bytes_for_item(name_str):
        # กำหนดรายชื่อหวยที่จะใช้ใบ B2 (VIP)
        vip_list = [
            "ฮานอยพิเศษ", "ฮานอยสามัคคี", "ฮานอยปกติ", 
            "ฮานอย VIP", "ฮานอยพัฒนา", "ลาวพัฒนา", "รัฐบาลไทย"
        ]
        
        if name_str in vip_list:
            # ถ้าชื่อตรงกับในลิสต์ -> ใช้ใบ B2 (create_image_normal)
            return create_image_normal(name_str, n_main1, n_pair1, n_pair2, n_pair3, n_pair4, n_pair5, n_pair6, fournum)
        else:
            # หวยอื่นๆ ที่เหลือทั้งหมด -> ใช้ใบ B1 (create_image_vip)
            return create_image_vip(name_str, v_main1, v_main2, v_pair1, v_pair2, v_pair3, v_pair4, v_pair5, v_pair6, triple1, triple2, triple3)

    if len(parsed_items) == 1:
        item = parsed_items[0]
        filename = f"{item['time'].replace(':', '.')}_{item['name']}.jpg" if item['time'] else f"{item['name']}.jpg"
        img_bytes = generate_bytes_for_item(item['name'])
        return StreamingResponse(io.BytesIO(img_bytes), media_type="image/jpeg", headers={"Content-Disposition": f"attachment; filename*=utf-8''{quote(filename)}"})

    zip_buf = io.BytesIO()
    with zipfile.ZipFile(zip_buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for index, item in enumerate(parsed_items, start=1):
            time_part = f"{item['time'].replace(':', '.')}_" if item['time'] else ""
            filename = f"{index:02d}_{time_part}{item['name']}.jpg"
            zf.writestr(filename, generate_bytes_for_item(item['name']))
    zip_buf.seek(0)
    return StreamingResponse(zip_buf, media_type="application/zip", headers={"Content-Disposition": 'attachment; filename="lottery_results.zip"'})

if __name__ == "__main__":
    import os
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=int(os.getenv("PORT", 8000)), reload=False)
