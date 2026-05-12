from flask import Flask, render_template_string, request, jsonify
import os
import subprocess
import json
import time
import boto3
from datetime import datetime

app = Flask(__name__)

# --- GLOBAL STATES & CONSTANTS ---
PROFIT_MODE = False 
LATENCY_MODE = False
MUMBAI_ON_DEMAND_RATE = 0.0008 

ec2_client = boto3.client('ec2', region_name='us-east-1')

def get_real_spot_price():
    try:
        response = ec2_client.describe_spot_price_history(
            InstanceTypes=['t3.micro'],
            ProductDescriptions=['Linux/UNIX'],
            StartTime=datetime.now(),
            MaxResults=1
        )
        return float(response['SpotPriceHistory'][0]['SpotPrice'])
    except:
        return 0.0044

def get_terraform_data():
    try:
        subprocess.run(['terraform', 'apply', '-refresh-only', '-auto-approve'], capture_output=True, text=True)
        result = subprocess.run(['terraform', 'output', '-json'], capture_output=True, text=True)
        outputs = json.loads(result.stdout)
        return {
            "primary_ip": outputs['primary_server_ip']['value'],
            "backup_ip": outputs['backup_server_ip']['value']
        }
    except:
        return {"primary_ip": "0.0.0.0", "backup_ip": "0.0.0.0"}

def check_latency(ip):
    if ip == "0.0.0.0": return (False, 1000.0)
    start = time.time()
    param = "-n" if os.name == 'nt' else "-c"
    response = os.system(f"ping {param} 1 {ip} > nul")
    end = time.time()
    l_val = round((end - start) * 1000, 2)
    return (response == 0, l_val if response == 0 else 1000.0)

@app.route('/toggle_logic', methods=['POST'])
def toggle_logic():
    global PROFIT_MODE, LATENCY_MODE
    data = request.get_json()
    if 'profit' in data: PROFIT_MODE = data['profit']
    if 'latency' in data: LATENCY_MODE = data['latency']
    return jsonify({"status": "success"})

@app.route('/')
def home():
    global PROFIT_MODE, LATENCY_MODE, MUMBAI_ON_DEMAND_RATE
    data = get_terraform_data()
    va_spot_rate = get_real_spot_price()
    mumbai_rate = MUMBAI_ON_DEMAND_RATE
    
    mumbai_ok, mumbai_lat = check_latency(data['primary_ip'])
    usa_ok, usa_lat = check_latency(data['backup_ip'])
    
    mumbai_is_cheaper = mumbai_rate < va_spot_rate
    m_cost_col = "#00d4ff" if mumbai_is_cheaper else "inherit"
    v_cost_col = "#00d4ff" if not mumbai_is_cheaper else "inherit"
    
    mumbai_is_faster = mumbai_lat < usa_lat
    m_lat_col = "#ffae00" if mumbai_is_faster else "inherit"
    v_lat_col = "#ffae00" if not mumbai_is_faster else "inherit"

    higher_rate = max(mumbai_rate, va_spot_rate)
    lower_rate = min(mumbai_rate, va_spot_rate)
    savings_val = round(((higher_rate - lower_rate) / higher_rate) * 100, 1)
    savings_txt = f"{savings_val}%"

    if LATENCY_MODE:
        if mumbai_is_faster and mumbai_ok:
            status, region, current_ip, accent = "PERFORMANCE OPTIMIZED", "MUMBAI (FASTEST)", data['primary_ip'], "#ffae00"
            current_lat, cost_txt = mumbai_lat, f"${mumbai_rate}/hr"
        elif usa_ok:
            status, region, current_ip, accent = "PERFORMANCE OPTIMIZED", "VIRGINIA (FASTEST)", data['backup_ip'], "#ffae00"
            current_lat, cost_txt = usa_lat, f"${va_spot_rate}/hr"
        else:
            status, region, current_ip, accent = "CRITICAL FAIL", "OFFLINE", "0.0.0.0", "#ff4444"
            current_lat, cost_txt = 0, "$0.00"
    elif PROFIT_MODE:
        if (not mumbai_is_cheaper) and usa_ok:
            status, region, current_ip, accent = "COST OPTIMIZED", "VIRGINIA (CHEAPEST)", data['backup_ip'], "#00d4ff"
            current_lat, cost_txt = usa_lat, f"${va_spot_rate}/hr"
        elif mumbai_ok:
            status, region, current_ip, accent = "COST OPTIMIZED", "MUMBAI (CHEAPEST)", data['primary_ip'], "#00d4ff"
            current_lat, cost_txt = mumbai_lat, f"${mumbai_rate}/hr"
        else:
            status, region, current_ip, accent = "FAILOVER ACTIVE", "VIRGINIA", data['backup_ip'], "#ff4444"
            current_lat, cost_txt = usa_lat, f"${va_spot_rate}/hr"
    elif mumbai_ok:
        status, region, current_ip, accent = "OPERATIONAL", "MUMBAI (PRIMARY)", data['primary_ip'], "#00ff88"
        current_lat, cost_txt = mumbai_lat, f"${mumbai_rate}/hr"
    else:
        status, region, current_ip, accent = "FAILOVER ACTIVE", "VIRGINIA (STANDBY)", data['backup_ip'], "#ff4444"
        current_lat, cost_txt = usa_lat, f"${va_spot_rate}/hr"

    html_template = f'''
    <!DOCTYPE html>
    <html>
    <head>
        <title>Cloud Orchestrator NOC</title>
        <script src="https://cdnjs.cloudflare.com/ajax/libs/Chart.js/3.9.1/chart.min.js"></script>
        <style>
            :root {{ --accent: {accent}; --bg: #0b0e14; }}
            body {{ background: var(--bg); color: #c9d1d9; font-family: 'Inter', sans-serif; margin: 0; display: flex; height: 100vh; overflow: hidden; }}
            .sidebar {{ width: 350px; background: #161b22; border-right: 1px solid #30363d; padding: 20px; overflow-y: auto; }}
            .main {{ flex-grow: 1; padding: 30px; display: flex; flex-direction: column; overflow-y: auto; }}
            .card {{ background: #1c2128; border: 1px solid #30363d; border-radius: 12px; padding: 20px; margin-bottom: 20px; }}
            .label {{ font-size: 10px; color: #8b949e; text-transform: uppercase; letter-spacing: 1px; margin-bottom: 10px; }}
            .stat-value {{ font-size: 22px; font-weight: bold; color: var(--accent); }}
            .switch {{ position: relative; display: inline-block; width: 44px; height: 22px; }}
            .switch input {{ opacity: 0; width: 0; height: 0; }}
            .slider {{ position: absolute; cursor: pointer; top: 0; left: 0; right: 0; bottom: 0; background-color: #30363d; transition: .4s; border-radius: 34px; }}
            .slider:before {{ position: absolute; content: ""; height: 16px; width: 16px; left: 3px; bottom: 3px; background-color: white; transition: .4s; border-radius: 50%; }}
            input:checked + .slider.profit {{ background-color: #00d4ff; }}
            input:checked + .slider.latency {{ background-color: #ffae00; }}
            input:checked + .slider:before {{ transform: translateX(22px); }}
            table {{ width: 100%; border-collapse: collapse; margin-top: 15px; text-align: left; }}
            th {{ color: #8b949e; font-size: 11px; padding: 10px; border-bottom: 1px solid #30363d; }}
            td {{ padding: 15px 10px; font-size: 14px; border-bottom: 1px solid #30363d; }}
        </style>
    </head>
    <body>
        <div class="sidebar">
            <h3 style="color:white; margin-bottom:25px;">ORCHESTRATION</h3>
            
            <div class="card" style="border: 1px solid #00d4ff44;">
                <div style="display:flex; justify-content:space-between; align-items:center;">
                    <p class="label" style="margin:0; color:#00d4ff;">FinOps Mode</p>
                    <label class="switch">
                        <input type="checkbox" id="pTog" {"checked" if PROFIT_MODE else ""} onchange="updateMode()">
                        <span class="slider profit"></span>
                    </label>
                </div>
            </div>

            <div class="card" style="border: 1px solid #ffae0044;">
                <div style="display:flex; justify-content:space-between; align-items:center;">
                    <p class="label" style="margin:0; color:#ffae00;">Latency Mode</p>
                    <label class="switch">
                        <input type="checkbox" id="lTog" {"checked" if LATENCY_MODE else ""} onchange="updateMode()">
                        <span class="slider latency"></span>
                    </label>
                </div>
            </div>

            <div class="card" style="background: #0d1117;">
                <p class="label">Primary Latency (ms)</p>
                <div style="height: 180px;"><canvas id="latencyChart"></canvas></div>
            </div>

            <div class="card">
                <p class="label">Realized Savings</p>
                <div style="font-size: 2.2em; color: #00ff88; font-weight: bold;">{savings_txt}</div>
            </div>
        </div>

        <div class="main">
            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 25px;">
                <div style="display:flex; align-items:center;">
                    <div style="height:12px; width:12px; background:{accent}; border-radius:50%; box-shadow: 0 0 10px {accent}; margin-right:15px;"></div>
                    <span style="font-size: 1.8em; font-weight: bold; color: white;">SYSTEM {status}</span>
                </div>
                <div style="text-align: right;">
                    <p class="label" style="margin:0;">Active Ingress</p>
                    <div style="color: white; font-weight: bold;">{region}</div>
                </div>
            </div>

            <div style="display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 20px; margin-bottom: 20px;">
                <div class="card"><p class="label">Endpoint</p><div class="stat-value">{current_ip}</div></div>
                <div class="card"><p class="label">Response</p><div class="stat-value">{current_lat} ms</div></div>
                <div class="card"><p class="label">Rate</p><div class="stat-value">{cost_txt}</div></div>
            </div>

            <div class="card" style="flex-grow: 1;">
                <p class="label" style="margin:0;">Multi-Region Telemetry</p>
                <table>
                    <thead>
                        <tr><th>REGION</th><th>ENDPOINT</th><th>COST/HR</th><th>STATUS</th><th>LATENCY</th></tr>
                    </thead>
                    <tbody>
                        <tr>
                            <td>ASIA-SOUTH-1</td>
                            <td><code>{data['primary_ip']}</code></td>
                            <td style="color:{m_cost_col};">${mumbai_rate}</td>
                            <td><span style="color:{'#00ff88' if mumbai_ok else '#ff4444'}">●</span> {'Healthy' if mumbai_ok else 'Down'}</td>
                            <td style="color:{m_lat_col};">{mumbai_lat} ms</td>
                        </tr>
                        <tr>
                            <td>US-EAST-1</td>
                            <td><code>{data['backup_ip']}</code></td>
                            <td style="color:{v_cost_col};">${va_spot_rate}</td>
                            <td><span style="color:{'#00ff88' if usa_ok else '#ff4444'}">●</span> {'Healthy' if usa_ok else 'Down'}</td>
                            <td style="color:{v_lat_col};">{usa_lat} ms</td>
                        </tr>
                    </tbody>
                </table>
            </div>
        </div>

        <script>
            function updateMode() {{
                fetch('/toggle_logic', {{
                    method: 'POST',
                    headers: {{ 'Content-Type': 'application/json' }},
                    body: JSON.stringify({{ 
                        profit: document.getElementById('pTog').checked,
                        latency: document.getElementById('lTog').checked
                    }})
                }}).then(() => location.reload());
            }}

            const currentLat = parseFloat("{current_lat}");
            let history = JSON.parse(localStorage.getItem('noc_latency_log') || '[]');
            history.push(currentLat);
            if (history.length > 20) history.shift();
            localStorage.setItem('noc_latency_log', JSON.stringify(history));

            const ctx = document.getElementById('latencyChart').getContext('2d');
            new Chart(ctx, {{
                type: 'line',
                data: {{
                    labels: history.map((_, i) => ""),
                    datasets: [{{
                        data: history,
                        borderColor: '{accent}',
                        backgroundColor: '{accent}22',
                        borderWidth: 2,
                        pointRadius: 0,
                        fill: true,
                        tension: 0.4
                    }}]
                }},
                options: {{
                    responsive: true,
                    maintainAspectRatio: false,
                    animation: false,
                    plugins: {{ legend: {{ display: false }} }},
                    scales: {{
                        y: {{ beginAtZero: true, grid: {{ color: '#30363d' }}, ticks: {{ display: false }} }},
                        x: {{ grid: {{ display: false }} }}
                    }}
                }}
            }});
            setTimeout(() => {{ window.location.reload(); }}, 5000);
        </script>
    </body>
    </html>
    '''
    return render_template_string(html_template)

if __name__ == '__main__':
    app.run(debug=True, port=5000)