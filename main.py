html = f"""
<!DOCTYPE html>
<html lang="pl">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">

<title>Quantum Edge</title>

<style>

body {{
    background:#031226;
    color:white;
    font-family:Arial;
    margin:0;
    padding:0;
}}

.header {{
    padding:25px;
    display:flex;
    justify-content:space-between;
    align-items:center;
}}

.logo {{
    font-size:28px;
    font-weight:bold;
}}

.green {{
    color:#8cff00;
}}

.menu-btn {{
    border:1px solid #1d324f;
    padding:12px 22px;
    border-radius:16px;
    color:#8cff00;
    background:#071a33;
}}

.box {{
    background:#07152c;
    margin:18px;
    padding:24px;
    border-radius:28px;
    border:1px solid #11284a;
}}

input {{
    width:100%;
    background:#081325;
    border:1px solid #1a3355;
    color:white;
    padding:18px;
    border-radius:18px;
    margin-top:10px;
    margin-bottom:20px;
    font-size:18px;
    box-sizing:border-box;
}}

button {{
    width:100%;
    padding:20px;
    background:#64ff47;
    color:black;
    border:none;
    border-radius:18px;
    font-size:22px;
    font-weight:bold;
}}

.icon-row {{
    display:flex;
    gap:14px;
    justify-content:flex-end;
    margin-bottom:10px;
}}

.icon-btn {{
    width:72px;
    height:72px;
    border-radius:50%;
    background:#17321f;
    border:2px solid #4cff59;
    display:flex;
    align-items:center;
    justify-content:center;
    font-size:34px;
}}

.small {{
    color:#c7d1dc;
    font-size:18px;
    line-height:1.5;
}}

</style>
</head>

<body>

<div class="header">
    <div class="logo">
        ⚛ QUANTUM <span class="green">EDGE</span>
    </div>

    <div style="display:flex; gap:12px;">
        <div class="menu-btn">Analiza</div>
        <div class="menu-btn">Historia</div>
    </div>
</div>

<div class="box">

<h3 style="color:#8cff00;">ANALIZA MECZU</h3>

<h1>Quantum Edge Web MVP</h1>

<p class="small">
Ikonka ⚡ pobiera statystyki.<br>
Ikonka 💰 pobiera kursy bukmacherów.
</p>

</div>

<div class="box">

<div class="icon-row">

<div class="icon-btn">
⚡
</div>

<div class="icon-btn">
💰
</div>

</div>

<h1>Dane meczu</h1>

<form method="POST">

<label>Gospodarz</label>
<input type="text" name="home" value="{home}">

<label>Gość</label>
<input type="text" name="
