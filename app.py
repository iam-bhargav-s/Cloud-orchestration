from flask import Flask, render_template_string, request, jsonify
import os
import subprocess
import json
import time
import boto3
from datetime import datetime
from agent import agent_executor  
from reconciliation import run_reconciliation_cycle

app = Flask(__name__)

# --- GLOBAL STATES & CONSTANTS ---
PROFIT_MODE = False 
LATENCY_MODE = False
MUMBAI_ON_DEMAND_RATE = 0.1008 

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

@app.route('/chat', methods=['POST'])
def chat():
    user_msg = request.json.get('message')
    thread_id = request.json.get('thread_id', 'session1') 
    
    try:
        response = agent_executor.invoke(
            {"messages": [("user", user_msg)]},
            config={"configurable": {"thread_id": thread_id}}
        )
        
        # Check if the agent called the mode switch tool
        switch_mode = None
        switch_action = "on"
        for msg in response["messages"]:
            # 1. Robust check directly against the AI's structured tool calls
            if hasattr(msg, 'tool_calls') and msg.tool_calls:
                for tc in msg.tool_calls:
                    name = tc.get('name', '').lower()
                    if 'switch' in name or 'mode' in name:
                        args = tc.get('args', {})
                        m_arg = str(args.get('mode', '')).lower()
                        a_arg = str(args.get('action', 'on')).lower()
                        if 'fin' in m_arg: switch_mode = 'finops'
                        elif 'lat' in m_arg: switch_mode = 'latency'
                        switch_action = 'off' if ('off' in a_arg or a_arg == 'false') else 'on'
            
            # 2. Fallback check for raw string output
            content_str = str(msg.content).lower()
            if "mode_switch:finops" in content_str:
                switch_mode = "finops"
                switch_action = "off" if "off" in content_str else "on"
            elif "mode_switch:latency" in content_str:
                switch_mode = "latency"
                switch_action = "off" if "off" in content_str else "on"

        final_message = response["messages"][-1].content
        
        # Clean up output string format
        if isinstance(final_message, list):
            text_blocks = [b.get('text', '') for b in final_message if isinstance(b, dict) and 'text' in b]
            final_message = "\n".join(text_blocks) if text_blocks else str(final_message)
        elif not isinstance(final_message, str):
            final_message = str(final_message)

        # Remove system flags from final response text if present
        final_message = final_message.replace("MODE_SWITCH:finops:on", "").replace("MODE_SWITCH:finops:off", "")
        final_message = final_message.replace("MODE_SWITCH:latency:on", "").replace("MODE_SWITCH:latency:off", "")
        if not final_message.strip():
            final_message = f"Switched {switch_mode.upper()} mode {switch_action}!"

        return jsonify({
            "response": final_message,
            "switch_mode": switch_mode,
            "switch_action": switch_action
        })
        
    except Exception as e:
        print(f"Chat error: {e}")
        return jsonify({"response": f"Error executing agent: {str(e)}"})

@app.route('/api/reconcile', methods=['POST'])
def reconcile_infrastructure():
    try:
        # Trigger the engine for your dual-region setup
        result = run_reconciliation_cycle(regions=["us-east-1", "ap-south-1"])
        return jsonify(result), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

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
        <!-- Added marked.js to parse the AI's markdown formatting -->
        <script src="https://cdn.jsdelivr.net/npm/marked/marked.min.js"></script>
        <style>
            :root {{ --accent: {accent}; --bg: #0b0e14; }}
            body {{ background: var(--bg); color: #c9d1d9; font-family: 'Inter', sans-serif; margin: 0; display: flex; height: 100vh; overflow: hidden; }}
            .sidebar {{ width: 320px; min-width: 320px; flex-shrink: 0; background: #161b22; border-right: 1px solid #30363d; padding: 20px; overflow-y: auto; }}
            .main {{ flex-grow: 1; padding: 30px; display: flex; flex-direction: column; overflow-y: auto; min-width: 0; }}
            .card {{ background: #1c2128; border: 1px solid #30363d; border-radius: 12px; padding: 20px; }}
            .label {{ font-size: 10px; color: #8b949e; text-transform: uppercase; letter-spacing: 1px; margin-bottom: 10px; }}
            .stat-value {{ font-weight: bold; color: var(--accent); }}
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
            
            ::-webkit-scrollbar {{ width: 8px; }}
            ::-webkit-scrollbar-track {{ background: #0b0e14; }}
            ::-webkit-scrollbar-thumb {{ background: #30363d; border-radius: 4px; }}

            /* Chat Typography Styles */
            .bot-msg {{ margin-top: 5px; font-size: 13.5px; line-height: 1.6; color: #c9d1d9; }}
            .bot-msg p {{ margin: 0 0 10px 0; }}
            .bot-msg p:last-child {{ margin: 0; }}
            .bot-msg ul, .bot-msg ol {{ margin: 5px 0; padding-left: 20px; }}
            .bot-msg li {{ margin-bottom: 4px; }}
            .bot-msg strong {{ color: #ffffff; }}
            .bot-msg code {{ background: #161b22; padding: 2px 5px; border-radius: 4px; font-family: monospace; font-size: 12px; }}
            
            /* ADD THESE RULES TO FIX LARGE HEADERS */
            .bot-msg h1 {{ font-size: 16px; font-weight: bold; margin: 10px 0 5px 0; color: #ffffff; }}
            .bot-msg h2 {{ font-size: 14.5px; font-weight: bold; margin: 8px 0 4px 0; color: #ffffff; }}
            .bot-msg h3 {{ font-size: 13.5px; font-weight: bold; margin: 6px 0 2px 0; color: #ffffff; }}
        </style>
    </head>
    <body>
        <div class="sidebar">
            <h3 style="color:white; margin-bottom:25px;">ORCHESTRATION</h3>
            
            <div class="card" style="border: 1px solid #00d4ff44; margin-bottom: 20px;">
                <div style="display:flex; justify-content:space-between; align-items:center;">
                    <p class="label" style="margin:0; color:#00d4ff;">FinOps Mode</p>
                    <label class="switch">
                        <input type="checkbox" id="pTog" {"checked" if PROFIT_MODE else ""} onchange="updateMode()">
                        <span class="slider profit"></span>
                    </label>
                </div>
            </div>

            <div class="card" style="border: 1px solid #ffae0044; margin-bottom: 20px;">
                <div style="display:flex; justify-content:space-between; align-items:center;">
                    <p class="label" style="margin:0; color:#ffae00;">Latency Mode</p>
                    <label class="switch">
                        <input type="checkbox" id="lTog" {"checked" if LATENCY_MODE else ""} onchange="updateMode()">
                        <span class="slider latency"></span>
                    </label>
                </div>
            </div>

            <div class="card" style="background: #0d1117; margin-bottom: 20px;">
                <p class="label">Primary Latency (ms)</p>
                <div style="height: 180px;"><canvas id="latencyChart"></canvas></div>
            </div>

            <div class="card">
                <p class="label">Realized Savings</p>
                <div style="font-size: 2.2em; color: #00ff88; font-weight: bold;">{savings_txt}</div>
            </div>
        </div>

        <div class="main">
            <!-- Header Section -->
            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 25px; flex-shrink: 0;">
                <div style="display:flex; align-items:center;">
                    <div style="height:12px; width:12px; background:{accent}; border-radius:50%; box-shadow: 0 0 10px {accent}; margin-right:15px;"></div>
                    <span style="font-size: 1.8em; font-weight: bold; color: white;">SYSTEM {status}</span>
                </div>
                <div style="text-align: right;">
                    <p class="label" style="margin:0;">Active Ingress</p>
                    <div style="color: white; font-weight: bold;">{region}</div>
                </div>
            </div>

            <!-- Main Layout Split -->
            <div style="display: flex; gap: 20px; flex-grow: 1; min-height: 0;">
                
                <!-- Left Column (Metrics + Table) -->
                <div style="flex: 1.6; display: flex; flex-direction: column; gap: 20px; min-width: 0;">
                    
                    <!-- 3 Smaller Metric Cards on Top -->
                    <div style="display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 20px;">
                        <div class="card"><p class="label">Endpoint</p><div class="stat-value" style="font-size: 18px;">{current_ip}</div></div>
                        <div class="card"><p class="label">Response</p><div class="stat-value" style="font-size: 18px;">{current_lat} ms</div></div>
                        <div class="card"><p class="label">Rate</p><div class="stat-value" style="font-size: 18px;">{cost_txt}</div></div>
                    </div>

                    <!-- Telemetry Table Directly Below -->
                    <div class="card" style="flex-grow: 1; overflow-y: auto;">
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

                <!-- Right Column (Full Height Chatbot) -->
                <div class="card" style="flex: 1; display: flex; flex-direction: column; min-width: 300px;">
                    <p class="label" style="margin:0; margin-bottom: 15px;">EcoOps FinOps Agent</p>
                    <div id="chat-history" style="flex-grow: 1; overflow-y: auto; margin-bottom: 15px; font-size: 13px; display: flex; flex-direction: column; gap: 10px; padding-right: 5px;">
                        
                        <div style="background: #0d1117; padding: 10px; border-radius: 8px; border: 1px solid #30363d; align-self: flex-start; max-width: 95%;">
                            <span style="color: #00ff88; font-weight: bold;">EcoOps:</span>
                            <div class="bot-msg">System online. Need budget estimates or deployments?</div>
                        </div>

                    </div>
                    <div style="display: flex; gap: 10px; flex-shrink: 0;">
                        <input type="text" id="chat-input" placeholder="Ask agent..." style="flex-grow: 1; padding: 10px; border-radius: 8px; border: 1px solid #30363d; background: #0d1117; color: white; outline: none; font-family: 'Inter', sans-serif;">
                        <button onclick="sendChat()" style="background: #c9d1d9; color: #0b0e14; border: none; padding: 10px 15px; border-radius: 8px; font-weight: bold; cursor: pointer;">Send</button>
                        <button onclick="clearChat()" style="background: #ff4444; color: white; border: none; padding: 10px 15px; border-radius: 8px; font-weight: bold; cursor: pointer;">Clear</button>
                    </div>
                </div>

            </div>
        </div>

        <script>
            // GENERATE DYNAMIC THREAD ID
            let currentThreadId = sessionStorage.getItem('ecoops_thread_id');
            if (!currentThreadId) {{
                currentThreadId = "session_" + Math.random().toString(36).substring(7);
                sessionStorage.setItem('ecoops_thread_id', currentThreadId);
            }}

            function clearChat() {{
                // Clear frontend memory
                sessionStorage.removeItem('ecoops_chat');
                
                // GENERATE A NEW THREAD ID to clear backend memory!
                currentThreadId = "session_" + Math.random().toString(36).substring(7);
                sessionStorage.setItem('ecoops_thread_id', currentThreadId);
                
                // Reset the chat window
                document.getElementById('chat-history').innerHTML = `
                    <div style="background: #0d1117; padding: 10px; border-radius: 8px; border: 1px solid #30363d; align-self: flex-start; max-width: 95%;">
                        <span style="color: #00ff88; font-weight: bold;">EcoOps:</span>
                        <div class="bot-msg">System online. Memory cleared. Need budget estimates or deployments?</div>
                    </div>
                `;
            }}
            
            // Persistent Chat Logic
            const chatHistory = document.getElementById('chat-history');
            const savedChat = sessionStorage.getItem('ecoops_chat');
            if (savedChat) {{
                chatHistory.innerHTML = savedChat;
                chatHistory.scrollTop = chatHistory.scrollHeight;
            }}

            let isAgentThinking = false; // Flag to prevent auto-reload while waiting for AI

            // HELPER FUNCTION: properly double-braced for Python f-string
            function applyUiModeSwitch(mode, action) {{
                const finopsToggle = document.getElementById('pTog');
                const latencyToggle = document.getElementById('lTog');

                const targetToggle = (mode === 'finops') ? finopsToggle : (mode === 'latency' ? latencyToggle : null);

                if (targetToggle) {{
                    const shouldBeChecked = (action === 'on' || action === 'true');
                    if (targetToggle.checked !== shouldBeChecked) {{
                        targetToggle.checked = shouldBeChecked;
                        updateMode(); // Directly trigger the backend update and reload!
                    }}
                }}
            }}

            async function sendChat() {{
                const input = document.getElementById('chat-input');
                if(!input.value) return;

                const userMsg = input.value;
                input.value = "";
                isAgentThinking = true; 

                // 1. Add User Message UI
                chatHistory.innerHTML += '<div style="background: #1c2128; padding: 10px; border-radius: 8px; border: 1px solid #30363d; align-self: flex-end; max-width: 85%;"><span style="color: #ffae00; font-weight: bold;">You:</span><div style="margin-top: 5px; font-size: 13.5px; line-height: 1.6;">' + userMsg + '</div></div>';
                
                // 2. SAVE TO MEMORY NOW (Before adding the loading indicator!)
                sessionStorage.setItem('ecoops_chat', chatHistory.innerHTML);
                
                // 3. ADD LOADING INDICATOR (Temporary, not saved to memory)
                const loadingId = "load_" + Math.random().toString(36).substring(7);
                chatHistory.innerHTML += `<div id="${{loadingId}}" style="background: #0d1117; padding: 10px; border-radius: 8px; border: 1px solid #30363d; align-self: flex-start; max-width: 95%;"><span style="color: #8b949e; font-style: italic;">EcoOps is thinking/fetching data...</span></div>`;
                
                chatHistory.scrollTop = chatHistory.scrollHeight;

                try {{
                    const res = await fetch('/chat', {{
                        method: 'POST',
                        headers: {{ 'Content-Type': 'application/json' }},
                        body: JSON.stringify({{ message: userMsg, thread_id: currentThreadId }}) 
                    }});
                    
                    if (!res.ok) throw new Error(`Server returned status: ${{res.status}}`);
                    
                    const data = await res.json();

                    // Remove loading indicator
                    document.getElementById(loadingId).remove();

                    // 1. Add Agent Message UI & Save to Memory FIRST
                    const formattedHTML = typeof marked !== 'undefined' ? marked.parse(data.response) : data.response;
                    chatHistory.innerHTML += '<div style="background: #0d1117; padding: 10px; border-radius: 8px; border: 1px solid #30363d; align-self: flex-start; max-width: 95%;"><span style="color: #00ff88; font-weight: bold;">EcoOps:</span><div class="bot-msg">' + formattedHTML + '</div></div>';
                    
                    sessionStorage.setItem('ecoops_chat', chatHistory.innerHTML);
                    chatHistory.scrollTop = chatHistory.scrollHeight;

                    // 2. NOW trigger the UI switch (which reloads the page)
                    if (data.switch_mode) {{
                        applyUiModeSwitch(data.switch_mode, data.switch_action);
                    }}

                }} catch(e) {{
                    // Remove loading indicator on error
                    const loader = document.getElementById(loadingId);
                    if(loader) loader.remove();

                    // SHOW ERROR VISIBLY IN THE CHAT
                    chatHistory.innerHTML += `<div style="background: #3a1d1d; padding: 10px; border-radius: 8px; border: 1px solid #ff4444; align-self: flex-start; max-width: 95%;"><span style="color: #ff4444; font-weight: bold;">System Error:</span><div class="bot-msg">${{e.message}} (Check VS Code Terminal)</div></div>`;
                    sessionStorage.setItem('ecoops_chat', chatHistory.innerHTML);
                    chatHistory.scrollTop = chatHistory.scrollHeight;
                }} finally {{
                    isAgentThinking = false;
                }}
            }}

            document.getElementById('chat-input').addEventListener('keypress', function (e) {{
                if (e.key === 'Enter') sendChat();
            }});

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
            
            // SMART RELOAD (Pauses while typing or waiting for AI response)
            setTimeout(() => {{ 
                if (!isAgentThinking && document.activeElement !== document.getElementById('chat-input')) {{
                    window.location.reload(); 
                }}
            }}, 5000);
        </script>
    </body>
    </html>
    '''
    return render_template_string(html_template)

if __name__ == '__main__':
    app.run(debug=True, port=5000)