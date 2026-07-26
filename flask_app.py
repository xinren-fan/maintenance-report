from flask import Flask, request, jsonify
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib.utils import ImageReader
import os, base64, tempfile
from datetime import datetime
from PIL import Image
import io

app = Flask(__name__)

BASE = os.path.dirname(__file__)
pdfmetrics.registerFont(TTFont('IPA',  os.path.join(BASE, 'ipag.ttf')))
pdfmetrics.registerFont(TTFont('IPAB', os.path.join(BASE, 'ipagp.ttf')))

W, H = A4

def b64_to_image_reader(b64str):
    if not b64str:
        return None
    try:
        if ',' in b64str:
            b64str = b64str.split(',')[1]
        img_data = base64.b64decode(b64str)
        img = Image.open(io.BytesIO(img_data))
        if img.mode in ('RGBA', 'P'):
            img = img.convert('RGB')
        buf = io.BytesIO()
        img.save(buf, format='JPEG', quality=85)
        buf.seek(0)
        return ImageReader(buf)
    except:
        return None

def crop_to_fill(b64str, target_w_mm, target_h_mm):
    """画像をセルサイズいっぱいにクロップ（アスペクト比を保ちつつ中央切り出し）"""
    if not b64str:
        return None
    try:
        if ',' in b64str:
            b64str = b64str.split(',')[1]
        img_data = base64.b64decode(b64str)
        img = Image.open(io.BytesIO(img_data))
        if img.mode in ('RGBA', 'P'):
            img = img.convert('RGB')

        iw, ih = img.size
        target_ratio = target_w_mm / target_h_mm
        img_ratio = iw / ih

        if img_ratio > target_ratio:
            # 画像が横長すぎる → 横をクロップ
            new_w = int(ih * target_ratio)
            left = (iw - new_w) // 2
            img = img.crop((left, 0, left + new_w, ih))
        else:
            # 画像が縦長すぎる → 縦をクロップ
            new_h = int(iw / target_ratio)
            top = (ih - new_h) // 2
            img = img.crop((0, top, iw, top + new_h))

        buf = io.BytesIO()
        img.save(buf, format='JPEG', quality=85)
        buf.seek(0)
        return ImageReader(buf)
    except:
        return None

def draw_photos(c, photos, left_mm, top_mm, width_mm, height_mm):
    """写真をセルいっぱいにクロップ表示（全セル同じサイズに統一）"""
    photos = [p for p in (photos or []) if p]
    if not photos:
        return False

    pad = 2.0
    n = min(len(photos), 3)
    cell_w_mm = (width_mm - pad * 2) / n
    cell_h_mm = height_mm - pad * 2

    box_bottom_pt = H - (top_mm + height_mm) * mm

    for i, b64 in enumerate(photos[:n]):
        cropped_reader = crop_to_fill(b64, cell_w_mm, cell_h_mm)
        if not cropped_reader:
            continue
        try:
            cell_w_pt = cell_w_mm * mm
            cell_h_pt = cell_h_mm * mm
            cell_x = (left_mm + pad + i * cell_w_mm) * mm
            cell_y = box_bottom_pt + pad * mm
            c.drawImage(cropped_reader, cell_x, cell_y, width=cell_w_pt, height=cell_h_pt, mask='auto')
        except Exception:
            continue
    return True

def make_pdf(data, output_path):
    c = canvas.Canvas(output_path, pagesize=A4)
    s = lambda v: str(v) if v else ''

    L = 5    # 左マージン mm
    R = 200  # 右端 mm
    TW = R - L  # 195mm

    # コンテンツの実高さ(5〜229mm=224mm)をA4の使用可能高さ(5〜292mm=287mm)まで拡大
    CONTENT_TOP = 5
    CONTENT_BOTTOM = 235
    PAGE_BOTTOM = 292
    SCALE_Y = (PAGE_BOTTOM - CONTENT_TOP) / (CONTENT_BOTTOM - CONTENT_TOP)  # 約1.250

    c.saveState()
    # 上端(y=0)を固定点として縦方向にスケール
    c.translate(0, H)
    c.scale(1.0, SCALE_Y)
    c.translate(0, -H)

    def txt(text, x, y, size=7, bold=False, align='L'):
        c.setFont('IPAB' if bold else 'IPA', size)
        px, py = x*mm, H - y*mm
        if align == 'C': c.drawCentredString(px, py, text)
        elif align == 'R': c.drawRightString(px, py, text)
        else: c.drawString(px, py, text)

    def box(x, y, w, h, fill=None):
        if fill:
            c.setFillColor(fill)
            c.rect(x*mm, H-y*mm, w*mm, -h*mm, fill=1, stroke=1)
            c.setFillColor(colors.black)
        else:
            c.rect(x*mm, H-y*mm, w*mm, -h*mm, fill=0, stroke=1)

    def hl(x1, y, x2): c.line(x1*mm, H-y*mm, x2*mm, H-y*mm)
    def vl(x, y1, y2): c.line(x*mm, H-y1*mm, x*mm, H-y2*mm)

    c.setLineWidth(0.5)
    LG  = colors.HexColor('#efefef')
    LG2 = colors.HexColor('#f4f4f4')
    W2  = colors.HexColor('#f8f8f8')

    # ── ヘッダー (y: 5〜35mm) ──
    box(L,5,87,30)
    txt('作　業　報　告　書', L+43, 17, 13, bold=True, align='C')
    txt('（出　張　報　告　書）', L+43, 25, 7, align='C')
    box(L+87,5,62,27)
    txt('株式会社アスファクト', L+118, 19, 9, bold=True, align='C')
    box(L+149,5,23,7); box(L+172,5,23,7)
    txt('承　認', L+160, 11, 7, bold=True, align='C')
    txt('担　当', L+183, 11, 7, bold=True, align='C')
    box(L+149,12,23,15); box(L+172,12,23,15)
    txt(s(data.get('tantou')), L+183, 21, 8, align='C')

    # ── 作業日時 (y: 35〜45mm) ──
    box(L,35,TW,10); hl(L,40,R)
    work_date = data.get('workDate','')
    if work_date:
        try:
            d = datetime.strptime(work_date,'%Y-%m-%d')
            txt(str(d.month),L+12,39,9,align='C'); txt('月',L+20,39,9)
            txt(str(d.day),L+32,39,9,align='C');   txt('日',L+40,39,9)
        except: pass
    start = data.get('startTime',''); end = data.get('endTime','')
    if start:
        sh,sm = start.split(':')
        txt(sh,L+57,39,9,align='C'); txt('時',L+65,39,9)
        txt(sm,L+72,39,9,align='C'); txt('分より',L+78,39,8)
    if end:
        eh,em = end.split(':')
        txt(eh,L+57,45,9,align='C'); txt('時',L+65,45,9)
        txt(em,L+72,45,9,align='C'); txt('分まで',L+78,45,8)
    vl(L+102,35,45)
    vl(L+140,35,45)
    vl(L+168,35,45)
    box(L+102,35,38,5,fill=LG); box(L+140,35,28,5,fill=LG); box(L+168,35,27,5,fill=LG)
    box(L+102,40,38,5); box(L+140,40,28,5); box(L+168,40,27,5)
    txt('機　種　名',L+121,39,7,bold=True,align='C')
    txt('型　式',L+154,39,7,bold=True,align='C')
    txt('製造番号',L+181,39,7,bold=True,align='C')
    txt(s(data.get('kishu')),L+121,44,8,align='C')
    txt(s(data.get('kata')),L+154,44,8,align='C')
    txt(s(data.get('seizo')),L+181,44,7,align='C')

    # ── お得意先・現場写真 (y: 45〜95mm) ──
    # お得意先エリア
    box(L,45,78,50)
    txt('お得意先名',L+1,50,7,bold=True)
    txt(s(data.get('tokui_name')),L+1,58,9,bold=True)
    txt(s(data.get('tokui_company')),L+1,66,8)
    txt('オープン  '+s(data.get('tokui_openDate')),L+1,73,7)
    txt('住所  '+s(data.get('tokui_address')),L+1,80,7)
    txt('電話  '+s(data.get('tokui_tel')),L+1,87,7)

    # 現場写真エリア
    PX = L+78  # 写真エリア左端
    PW = TW-78  # 写真エリア幅
    box(PX,45,PW,7,fill=LG)
    txt('現場写真',PX+PW/2,50,7,bold=True,align='C')
    box(PX,52,PW,43)  # 写真枠（y:52〜95mm, 高さ43mm）

    site_photos = [p for p in (data.get('sitePhotos') or []) if p]
    if site_photos:
        draw_photos(c, site_photos, PX, 52, PW, 43)
    else:
        c.setFillColor(W2)
        c.rect(PX*mm, H-95*mm, PW*mm, 43*mm, fill=1, stroke=0)
        c.setFillColor(colors.gray)
        txt('写真なし',PX+PW/2,74,7,align='C')
        c.setFillColor(colors.black)

    # ── 故障内容・作業写真 (y: 95〜143mm) ──
    CX = L+94  # 故障内容/作業写真の境界
    CW = TW-94  # 作業写真エリア幅

    box(L,95,94,7,fill=LG)
    box(CX,95,25,7,fill=LG)
    box(CX+25,95,TW-119,7)
    txt('故障内容及び修理内容',L+1,100,7,bold=True)
    txt('納品日',CX+12,100,7,bold=True,align='C')
    txt(s(data.get('tokui_deliveryDate')),CX+38,100,7,align='C')

    box(L,102,94,41)  # 故障内容枠（41mm）
    content = s(data.get('content',''))

    # 実際の文字幅で折り返し計算（枠幅 94mm - 左右余白2mm = 92mm）
    max_width_pt = 92 * mm
    font_size = 7.5

    def wrap_line(raw_line, fsize):
        if not raw_line:
            return ['']
        c.setFont('IPA', fsize)
        lines = []
        cur = ''
        for ch in raw_line:
            test = cur + ch
            if c.stringWidth(test, 'IPA', fsize) > max_width_pt:
                lines.append(cur)
                cur = ch
            else:
                cur = test
        if cur:
            lines.append(cur)
        return lines

    all_lines = []
    for raw_line in content.split('\n'):
        all_lines.extend(wrap_line(raw_line, font_size))

    # 枠（41mm高さ）に収まる行数を計算。収まらない場合はフォントを縮小
    max_rows = 7
    line_height = 5.4
    if len(all_lines) > max_rows:
        # フォントを縮小して再折り返し
        font_size = max(5.5, 7.5 * max_rows / len(all_lines))
        max_width_pt = 92 * mm
        all_lines = []
        for raw_line in content.split('\n'):
            all_lines.extend(wrap_line(raw_line, font_size))
        line_height = 41 / max(len(all_lines), 1)
        line_height = min(line_height, 5.4)

    for i, line in enumerate(all_lines):
        y_pos = 109 + i * line_height
        if y_pos > 141:  # 枠を超えたら描画しない
            break
        txt(line, L+1, y_pos, font_size)

    # 作業写真エリア（y:95〜143mm）— 現場写真と同じ43mm高さに統一
    # ヘッダーバー：95〜102mm（7mm）
    # 写真枠：102〜145mm（43mm）
    box(CX,95,CW,7,fill=LG)
    txt('作業写真',CX+CW/2,100,7,bold=True,align='C')
    box(CX,102,CW,43)  # 写真枠（現場写真と同じ43mm）

    work_photos = [p for p in (data.get('workPhotos') or []) if p]
    if work_photos:
        # top_mm=102（写真枠の上端）, height_mm=43（写真枠の高さ、現場写真と統一）
        draw_photos(c, work_photos, CX, 102, CW, 43)
    else:
        c.setFillColor(W2)
        c.rect(CX*mm, H-145*mm, CW*mm, 43*mm, fill=1, stroke=0)
        c.setFillColor(colors.gray)
        txt('写真なし',CX+CW/2,125,7,align='C')
        c.setFillColor(colors.black)

    # 以降のセクションのシフト量（元のy=139基準から、新しいy=145基準への移動分）
    SHIFT = 6

    # ── 処置 (y: 146〜160mm) ──
    box(L,139+SHIFT,18,14,fill=LG); box(L+18,139+SHIFT,TW-18,7); box(L+18,146+SHIFT,TW-18,7)
    txt('処　置',L+9,149+SHIFT,8,bold=True,align='C')
    shochi = data.get('shochi','')
    txt('1.完了',L+20,144+SHIFT,8)
    txt('3.未処理（急対応）',L+105,144+SHIFT,8)
    txt('2.見積',L+20,151+SHIFT,8)
    txt('4.その他（　　　　　　　　　　　　　　）',L+105,151+SHIFT,8)
    shochi_pos = {
        '完了':(L+19,142+SHIFT),'見積':(L+19,149+SHIFT),
        '未処理（急対応）':(L+104,142+SHIFT),'その他':(L+104,149+SHIFT)
    }
    if shochi in shochi_pos:
        sx,sy = shochi_pos[shochi]
        c.setLineWidth(1.2)
        c.ellipse((sx-1)*mm,H-(sy+5)*mm,(sx+22)*mm,H-(sy-1)*mm,fill=0)
        c.setLineWidth(0.5)

    # ── 要請修理・有償無償 (y: 160〜167mm) ──
    box(L,153+SHIFT,60,7); box(L+60,153+SHIFT,TW-60,7)
    req = s(data.get('requestType')); pay = s(data.get('payType'))
    txt(req+'・巡回',L+30,158+SHIFT,7.5,align='C')
    # 有償・無償テキストを描画して位置を計算
    pay_text = '有償・無償の別　/　有償　・　無償'
    pay_cx = (L+130)*mm
    c.setFont('IPA', 7.5)
    tw = c.stringWidth(pay_text, 'IPA', 7.5)
    text_left = pay_cx - tw/2
    # 各文字位置を計算
    x = text_left
    char_positions = []
    for ch in pay_text:
        w = c.stringWidth(ch, 'IPA', 7.5)
        char_positions.append((x, x+w))
        x += w
    c.drawCentredString(pay_cx, H-(158+SHIFT)*mm, pay_text)
    # 「有償」は10,11文字目、「無償」は15,16文字目
    if pay == '有償':
        x1 = char_positions[10][0] - 1*mm
        x2 = char_positions[11][1] + 1*mm
        c.setLineWidth(1.2)
        c.ellipse(x1, H-(162+SHIFT)*mm, x2, H-(154+SHIFT)*mm, fill=0)
        c.setLineWidth(0.5)
    elif pay == '無償':
        x1 = char_positions[15][0] - 1*mm
        x2 = char_positions[16][1] + 1*mm
        c.setLineWidth(1.2)
        c.ellipse(x1, H-(162+SHIFT)*mm, x2, H-(154+SHIFT)*mm, fill=0)
        c.setLineWidth(0.5)

    # ── 部品・修理代金 (y: 167〜216mm) ──
    box(L,160+SHIFT,95,7,fill=LG); box(L+95,160+SHIFT,TW-95,7,fill=LG)
    txt('①　交換部品及び代金',L+47,165+SHIFT,7.5,bold=True,align='C')
    txt('②　修　理　代　金',L+145,165+SHIFT,7.5,bold=True,align='C')

    box(L,167+SHIFT,44,7,fill=LG2); box(L+44,167+SHIFT,14,7,fill=LG2)
    box(L+58,167+SHIFT,18,7,fill=LG2); box(L+76,167+SHIFT,19,7,fill=LG2)
    txt('品　　名',L+22,172+SHIFT,6.5,align='C'); txt('個数',L+51,172+SHIFT,6.5,align='C')
    txt('売上単価',L+67,172+SHIFT,6.5,align='C'); txt('金　額',L+85,172+SHIFT,6.5,align='C')

    parts = [
        (data.get('part1_name',''),data.get('part1_qty',''),data.get('part1_price','')),
        (data.get('part2_name',''),data.get('part2_qty',''),data.get('part2_price','')),
        (data.get('part3_name',''),data.get('part3_qty',''),data.get('part3_price','')),
        ('','',''),
    ]
    total_parts = 0
    for i,(nm,qty,up) in enumerate(parts):
        y = 174+SHIFT+i*7
        box(L,y,44,7); box(L+44,y,14,7); box(L+58,y,18,7); box(L+76,y,19,7)
        try:
            q = int(qty) if qty else 1  # 個数未入力は1個とみなす
            p = int(up) if up else 0
            amt = q * p if nm else 0
        except: amt = 0
        total_parts += amt
        txt(s(nm),L+1,y+5,7)
        if qty: txt(s(qty),L+51,y+5,7,align='C')
        if up:
            try: txt('¥'+int(up).__format__(','),L+75,y+5,7,align='R')
            except: pass
        if amt>0: txt('¥'+amt.__format__(','),L+94,y+5,7,align='R')

    box(L,202+SHIFT,76,7,fill=LG2); box(L+76,202+SHIFT,19,7)
    txt('①　　計',L+38,207+SHIFT,7,bold=True,align='C')
    if total_parts>0: txt('¥'+total_parts.__format__(','),L+94,207+SHIFT,7,bold=True,align='R')

    box(L+95,167+SHIFT,32,7,fill=LG2); box(L+127,167+SHIFT,22,7,fill=LG2); box(L+149,167+SHIFT,TW-149,7,fill=LG2)
    txt('項　目',L+111,172+SHIFT,6.5,align='C'); txt('時　間',L+138,172+SHIFT,6.5,align='C'); txt('金　額',L+167,172+SHIFT,6.5,align='C')

    try: sagyo_h = float(data.get('sagyo_h') or 0)
    except: sagyo_h = 0
    try: kousuu = float(data.get('kousuu_tanka') or 0)
    except: kousuu = 0
    try: kotsuu = int(data.get('kotsuu_fee') or 0)
    except: kotsuu = 0
    try: sonota = int(data.get('sonota_fee') or 0)
    except: sonota = 0
    sonota_nm = s(data.get('sonota_name',''))
    sagyo_fee = int(sagyo_h*kousuu)
    total_rep = sagyo_fee+kotsuu+sonota
    total_all = total_parts+total_rep

    repairs = [('作業費',f'{sagyo_h:g}時間',sagyo_fee),('出張諸経費','',kotsuu),(sonota_nm or 'その他','',sonota)]
    for i,(nm,h,amt) in enumerate(repairs):
        y = 174+SHIFT+i*7
        box(L+95,y,32,7); box(L+127,y,22,7); box(L+149,y,TW-149,7)
        txt(nm,L+111,y+5,7,align='C'); txt(h,L+138,y+5,7,align='C')
        if amt>0: txt('¥'+amt.__format__(','),R-1,y+5,7,align='R')

    box(L+95,195+SHIFT,54,7,fill=LG2); box(L+149,195+SHIFT,TW-149,7)
    txt('②　計',L+122,200+SHIFT,7,bold=True,align='C')
    if total_rep>0: txt('¥'+total_rep.__format__(','),R-1,200+SHIFT,7,bold=True,align='R')

    box(L+95,202+SHIFT,54,7,fill=LG2); box(L+149,202+SHIFT,TW-149,7)
    txt('①　＋　②',L+122,207+SHIFT,8,bold=True,align='C')
    if total_all>0: txt('¥'+total_all.__format__(','),R-1,207+SHIFT,9,bold=True,align='R')

    # ── フッター (y: 216〜236mm) ──
    box(L,209+SHIFT,TW,20)
    txt('本社　〒815-0031　福岡市南区清水3-24-36',L+1,215+SHIFT,6.5)
    txt('東京支社　〒144-0033　東京都大田区東糀谷2-14-17',L+1,221+SHIFT,6.5)
    txt('総務部　〒811-4184　宗像市くりえいと2-4-30',L+1,227+SHIFT,6.5)
    txt('℡0940-51-1648　fax0940-51-1877',L+115,227+SHIFT,6.5)
    txt('LaundryPress',L+148,223+SHIFT,13,bold=True)

    c.restoreState()
    c.save()


@app.route('/generate_pdf', methods=['POST'])
def generate_pdf():
    try:
        data = request.get_json(force=True)
        if not data:
            return jsonify({'status':'error','message':'データがありません'}), 400
        tmp = tempfile.NamedTemporaryFile(suffix='.pdf', delete=False)
        tmp.close()
        make_pdf(data, tmp.name)
        with open(tmp.name,'rb') as f:
            pdf_b64 = base64.b64encode(f.read()).decode('utf-8')
        os.unlink(tmp.name)
        return jsonify({'status':'success','pdf_base64':pdf_b64})
    except Exception as e:
        import traceback
        return jsonify({'status':'error','message':str(e),'trace':traceback.format_exc()}), 500


@app.route('/', methods=['GET'])
def index():
    return '保守報告書PDF生成サーバー 稼働中'


if __name__ == '__main__':
    app.run(debug=True)
