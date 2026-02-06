"""Web dashboard for OpenClaw bot monitoring - Glassy Ivory-Orange Design."""

import json
import threading
from datetime import datetime
from pathlib import Path
from typing import Optional
from flask import Flask, render_template_string, jsonify


class DashboardState:
    """Shared state between bot and dashboard."""
    
    def __init__(self):
        self.bot_started: Optional[datetime] = None
        self.bot_running: bool = False
        self.total_messages: int = 0
        self.total_tokens: int = 0
        self.active_users: set = set()
        self.providers: dict = {}
        self.recent_activity: list = []
        self.rate_limits: dict = {}
    
    def to_dict(self) -> dict:
        uptime = ""
        if self.bot_started:
            delta = datetime.now() - self.bot_started
            hours, remainder = divmod(int(delta.total_seconds()), 3600)
            minutes, seconds = divmod(remainder, 60)
            uptime = f"{hours}h {minutes}m {seconds}s"
        
        return {
            "bot_running": self.bot_running,
            "uptime": uptime,
            "total_messages": self.total_messages,
            "total_tokens": self.total_tokens,
            "active_users": len(self.active_users),
            "providers": self.providers,
            "recent_activity": self.recent_activity[-10:],
            "rate_limits": self.rate_limits,
        }
    
    def add_activity(self, activity_type: str, text: str, icon: str = "💬"):
        self.recent_activity.append({
            "type": activity_type, "text": text, "icon": icon,
            "time": datetime.now().strftime("%H:%M:%S"),
        })
        if len(self.recent_activity) > 50:
            self.recent_activity = self.recent_activity[-50:]


dashboard_state = DashboardState()


DASHBOARD_HTML = '''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>🦞 OpenClaw Dashboard</title>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap" rel="stylesheet">
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        :root {
            --ivory: #FFFFF0; --ivory-light: #FFFEF5;
            --orange-primary: #FF6B35; --orange-secondary: #FF8C42;
            --orange-glow: rgba(255, 107, 53, 0.4);
            --gold: #FFD700; --gold-glow: rgba(255, 215, 0, 0.6);
            --glass-bg: rgba(255, 255, 240, 0.08);
            --glass-border: rgba(255, 255, 240, 0.18);
        }
        body {
            font-family: 'Inter', sans-serif;
            min-height: 100vh;
            background: linear-gradient(135deg, #1a1a2e 0%, #16213e 50%, #0f0f23 100%);
            color: var(--ivory);
            overflow-x: hidden;
            display: flex;
            flex-direction: column;
        }
        .orb {
            position: fixed; border-radius: 50%; filter: blur(100px);
            opacity: 0.4; animation: float 25s ease-in-out infinite;
            pointer-events: none; z-index: 0;
        }
        .orb-1 { width: 500px; height: 500px; background: var(--orange-primary); top: -150px; right: -150px; }
        .orb-2 { width: 400px; height: 400px; background: var(--orange-secondary); bottom: -100px; left: -100px; animation-delay: -10s; }
        .orb-3 { width: 300px; height: 300px; background: var(--gold); top: 50%; left: 50%; transform: translate(-50%, -50%); animation-delay: -5s; opacity: 0.2; }
        @keyframes float {
            0%, 100% { transform: translate(0, 0) scale(1); }
            25% { transform: translate(30px, -30px) scale(1.05); }
            50% { transform: translate(-20px, 20px) scale(0.95); }
            75% { transform: translate(20px, 30px) scale(1.02); }
        }
        .container { max-width: 1400px; margin: 0 auto; padding: 2rem; position: relative; z-index: 1; flex: 1; width: 100%; }
        header {
            text-align: center; margin-bottom: 3rem; padding: 2rem;
            background: var(--glass-bg);
            backdrop-filter: blur(20px); -webkit-backdrop-filter: blur(20px);
            border: 1px solid var(--glass-border);
            border-radius: 24px;
            box-shadow: 0 8px 32px rgba(0,0,0,0.2), inset 0 1px 0 rgba(255,255,255,0.1);
            transition: transform 0.3s ease, box-shadow 0.3s ease;
        }
        header:hover { transform: translateY(-2px); box-shadow: 0 12px 40px rgba(255,107,53,0.15), inset 0 1px 0 rgba(255,255,255,0.15); }
        .logo { font-size: 3.5rem; margin-bottom: 0.5rem; animation: pulse 2s ease-in-out infinite; }
        @keyframes pulse { 0%, 100% { transform: scale(1); } 50% { transform: scale(1.05); } }
        h1 { font-size: 2.5rem; font-weight: 700; background: linear-gradient(135deg, var(--ivory) 0%, var(--orange-secondary) 100%); -webkit-background-clip: text; -webkit-text-fill-color: transparent; background-clip: text; }
        .subtitle { color: rgba(255,255,240,0.7); margin-top: 0.5rem; font-weight: 300; }
        .status-badge {
            display: inline-flex; align-items: center; gap: 0.5rem;
            padding: 0.5rem 1.5rem; border-radius: 50px; margin-top: 1rem;
            font-weight: 600; font-size: 0.9rem;
            backdrop-filter: blur(10px); transition: all 0.3s ease;
        }
        .status-badge:hover { transform: scale(1.05); }
        .status-online { background: rgba(34,197,94,0.2); border: 1px solid rgba(34,197,94,0.4); color: #22c55e; }
        .status-offline { background: rgba(239,68,68,0.2); border: 1px solid rgba(239,68,68,0.4); color: #ef4444; }
        .status-dot { width: 10px; height: 10px; border-radius: 50%; animation: blink 1.5s ease-in-out infinite; }
        .status-online .status-dot { background: #22c55e; box-shadow: 0 0 10px #22c55e; }
        .status-offline .status-dot { background: #ef4444; box-shadow: 0 0 10px #ef4444; }
        @keyframes blink { 0%, 100% { opacity: 1; } 50% { opacity: 0.5; } }
</style>
</head>
<body>
    <div class="orb orb-1"></div>
    <div class="orb orb-2"></div>
    <div class="orb orb-3"></div>
'''

DASHBOARD_HTML_2 = '''
    <style>
        .stats-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(280px, 1fr)); gap: 1.5rem; margin-bottom: 2rem; }
        .stat-card {
            background: var(--glass-bg);
            backdrop-filter: blur(20px); -webkit-backdrop-filter: blur(20px);
            border: 1px solid var(--glass-border);
            border-radius: 20px; padding: 1.5rem;
            box-shadow: 0 8px 32px rgba(0,0,0,0.15), inset 0 1px 0 rgba(255,255,255,0.08);
            transition: all 0.4s cubic-bezier(0.175, 0.885, 0.32, 1.275);
            position: relative; overflow: hidden;
        }
        .stat-card::before {
            content: ''; position: absolute; top: 0; left: 0; right: 0; height: 3px;
            background: linear-gradient(90deg, var(--orange-primary), var(--orange-secondary), var(--gold));
            opacity: 0; transition: opacity 0.3s ease;
        }
        .stat-card:hover { transform: translateY(-8px) scale(1.02); box-shadow: 0 20px 50px rgba(255,107,53,0.2), inset 0 1px 0 rgba(255,255,255,0.15); }
        .stat-card:hover::before { opacity: 1; }
        .stat-icon { font-size: 2.5rem; margin-bottom: 0.75rem; transition: transform 0.3s ease; }
        .stat-card:hover .stat-icon { transform: scale(1.2) rotate(5deg); }
        .stat-value { font-size: 2.2rem; font-weight: 700; color: var(--ivory); margin-bottom: 0.25rem; }
        .stat-label { color: rgba(255,255,240,0.6); font-size: 0.9rem; text-transform: uppercase; letter-spacing: 1px; }
        .grid-2 { display: grid; grid-template-columns: repeat(auto-fit, minmax(400px, 1fr)); gap: 1.5rem; }
        .card {
            background: var(--glass-bg);
            backdrop-filter: blur(20px); -webkit-backdrop-filter: blur(20px);
            border: 1px solid var(--glass-border);
            border-radius: 20px; padding: 1.5rem;
            box-shadow: 0 8px 32px rgba(0,0,0,0.15), inset 0 1px 0 rgba(255,255,255,0.08);
            transition: all 0.3s ease;
        }
        .card:hover { transform: translateY(-4px); box-shadow: 0 15px 40px rgba(255,107,53,0.15); }
        .card-title { font-size: 1.2rem; font-weight: 600; margin-bottom: 1rem; display: flex; align-items: center; gap: 0.5rem; }
        .provider-item {
            display: flex; justify-content: space-between; align-items: center;
            padding: 1rem; margin-bottom: 0.75rem;
            background: rgba(255,255,240,0.03); border-radius: 12px;
            border: 1px solid rgba(255,255,240,0.08);
            transition: all 0.3s ease;
        }
        .provider-item:hover { background: rgba(255,255,240,0.08); transform: translateX(5px); border-color: var(--orange-primary); }
        .provider-name { font-weight: 500; display: flex; align-items: center; gap: 0.5rem; }
        .provider-status { padding: 0.3rem 0.8rem; border-radius: 20px; font-size: 0.8rem; font-weight: 600; }
        .provider-ready { background: rgba(34,197,94,0.2); color: #22c55e; }
        .provider-error { background: rgba(239,68,68,0.2); color: #ef4444; }
        .provider-loading { background: rgba(234,179,8,0.2); color: #eab308; }
        .activity-item {
            display: flex; align-items: center; gap: 1rem;
            padding: 0.75rem; margin-bottom: 0.5rem;
            background: rgba(255,255,240,0.03); border-radius: 10px;
            transition: all 0.3s ease; border-left: 3px solid transparent;
        }
        .activity-item:hover { background: rgba(255,255,240,0.08); border-left-color: var(--orange-primary); transform: translateX(5px); }
        .activity-icon { font-size: 1.3rem; }
        .activity-text { flex: 1; font-size: 0.9rem; }
        .activity-time { color: rgba(255,255,240,0.5); font-size: 0.8rem; font-family: monospace; }
        .rate-bar { height: 8px; background: rgba(255,255,240,0.1); border-radius: 4px; overflow: hidden; margin-top: 0.5rem; }
        .rate-fill { height: 100%; background: linear-gradient(90deg, var(--orange-primary), var(--gold)); border-radius: 4px; transition: width 0.5s ease; }
        .rate-item { margin-bottom: 1rem; }
        .rate-header { display: flex; justify-content: space-between; font-size: 0.9rem; margin-bottom: 0.3rem; }
</style>
'''

DASHBOARD_HTML_3 = '''
    <style>
        footer {
            background: var(--glass-bg);
            backdrop-filter: blur(20px); -webkit-backdrop-filter: blur(20px);
            border-top: 1px solid var(--glass-border);
            padding: 2rem; text-align: center; margin-top: auto;
        }
        .footer-content { max-width: 1400px; margin: 0 auto; }
        .social-links { display: flex; justify-content: center; gap: 2rem; margin-bottom: 1.5rem; }
        .social-link {
            display: flex; align-items: center; justify-content: center;
            width: 50px; height: 50px; border-radius: 50%;
            background: rgba(255,215,0,0.1); border: 2px solid var(--gold);
            color: var(--gold); font-size: 1.5rem;
            text-decoration: none;
            transition: all 0.4s cubic-bezier(0.175, 0.885, 0.32, 1.275);
            position: relative; overflow: hidden;
        }
        .social-link::before {
            content: ''; position: absolute; inset: 0;
            background: linear-gradient(135deg, var(--gold), var(--orange-primary));
            opacity: 0; transition: opacity 0.3s ease;
        }
        .social-link:hover {
            transform: translateY(-8px) scale(1.15) rotate(5deg);
            box-shadow: 0 15px 30px var(--gold-glow), 0 0 20px var(--gold-glow);
            border-color: transparent;
        }
        .social-link:hover::before { opacity: 1; }
        .social-link svg, .social-link span { position: relative; z-index: 1; transition: all 0.3s ease; }
        .social-link:hover svg, .social-link:hover span { color: #1a1a2e; transform: scale(1.1); }
        .made-with {
            font-size: 1.1rem; color: rgba(255,255,240,0.8);
            display: flex; align-items: center; justify-content: center; gap: 0.5rem;
        }
        .made-with .heart { color: #ef4444; animation: heartbeat 1.5s ease-in-out infinite; font-size: 1.3rem; }
        .made-with .crown { color: var(--gold); animation: shine 2s ease-in-out infinite; font-size: 1.3rem; }
        .made-with a { color: var(--orange-secondary); text-decoration: none; font-weight: 600; transition: all 0.3s ease; }
        .made-with a:hover { color: var(--gold); text-shadow: 0 0 10px var(--gold-glow); }
        @keyframes heartbeat { 0%, 100% { transform: scale(1); } 50% { transform: scale(1.2); } }
        @keyframes shine { 0%, 100% { filter: brightness(1); } 50% { filter: brightness(1.5); } }
        @media (max-width: 768px) {
            .container { padding: 1rem; }
            h1 { font-size: 1.8rem; }
            .stats-grid { grid-template-columns: 1fr 1fr; }
            .grid-2 { grid-template-columns: 1fr; }
            .stat-value { font-size: 1.8rem; }
            .social-links { gap: 1rem; }
            .social-link { width: 45px; height: 45px; font-size: 1.2rem; }
        }
        @media (max-width: 480px) {
            .stats-grid { grid-template-columns: 1fr; }
            .logo { font-size: 2.5rem; }
            h1 { font-size: 1.5rem; }
        }
    </style>
'''

DASHBOARD_HTML_4 = '''
    <div class="container">
        <header>
            <div class="logo">🦞</div>
            <h1>OpenClaw Dashboard</h1>
            <p class="subtitle">AI-Powered Telegram Bot Control Center</p>
            <div id="status-badge" class="status-badge status-offline">
                <span class="status-dot"></span>
                <span id="status-text">Checking...</span>
            </div>
        </header>
        
        <div class="stats-grid">
            <div class="stat-card">
                <div class="stat-icon">⏱️</div>
                <div class="stat-value" id="uptime">--</div>
                <div class="stat-label">Uptime</div>
            </div>
            <div class="stat-card">
                <div class="stat-icon">💬</div>
                <div class="stat-value" id="messages">0</div>
                <div class="stat-label">Messages</div>
            </div>
            <div class="stat-card">
                <div class="stat-icon">🎯</div>
                <div class="stat-value" id="tokens">0</div>
                <div class="stat-label">Tokens Used</div>
            </div>
            <div class="stat-card">
                <div class="stat-icon">👥</div>
                <div class="stat-value" id="users">0</div>
                <div class="stat-label">Active Users</div>
            </div>
        </div>
        
        <div class="grid-2">
            <div class="card">
                <h3 class="card-title">🧠 AI Providers</h3>
                <div id="providers">
                    <div class="provider-item">
                        <span class="provider-name">⚡ Groq</span>
                        <span class="provider-status provider-loading">Loading...</span>
                    </div>
                    <div class="provider-item">
                        <span class="provider-name">☁️ Ollama Cloud</span>
                        <span class="provider-status provider-loading">Loading...</span>
                    </div>
                    <div class="provider-item">
                        <span class="provider-name">🖥️ Local Ollama</span>
                        <span class="provider-status provider-loading">Loading...</span>
                    </div>
                </div>
            </div>
            
            <div class="card">
                <h3 class="card-title">📊 Rate Limits</h3>
                <div id="rate-limits">
                    <div class="rate-item">
                        <div class="rate-header">
                            <span>Global</span>
                            <span>0 / 100</span>
                        </div>
                        <div class="rate-bar"><div class="rate-fill" style="width: 0%"></div></div>
                    </div>
                </div>
            </div>
        </div>
        
        <div class="card" style="margin-top: 1.5rem;">
            <h3 class="card-title">📜 Recent Activity</h3>
            <div id="activity">
                <div class="activity-item">
                    <span class="activity-icon">🔄</span>
                    <span class="activity-text">Waiting for activity...</span>
                    <span class="activity-time">--:--:--</span>
                </div>
            </div>
        </div>
    </div>
'''

DASHBOARD_HTML_5 = '''
    <footer>
        <div class="footer-content">
            <div class="social-links">
                <a href="https://fb.com/sharvinzlife" target="_blank" class="social-link" title="Facebook">
                    <svg width="24" height="24" viewBox="0 0 24 24" fill="currentColor">
                        <path d="M24 12.073c0-6.627-5.373-12-12-12s-12 5.373-12 12c0 5.99 4.388 10.954 10.125 11.854v-8.385H7.078v-3.47h3.047V9.43c0-3.007 1.792-4.669 4.533-4.669 1.312 0 2.686.235 2.686.235v2.953H15.83c-1.491 0-1.956.925-1.956 1.874v2.25h3.328l-.532 3.47h-2.796v8.385C19.612 23.027 24 18.062 24 12.073z"/>
                    </svg>
                </a>
                <a href="https://instagram.com/sharvinzlife" target="_blank" class="social-link" title="Instagram">
                    <svg width="24" height="24" viewBox="0 0 24 24" fill="currentColor">
                        <path d="M12 2.163c3.204 0 3.584.012 4.85.07 3.252.148 4.771 1.691 4.919 4.919.058 1.265.069 1.645.069 4.849 0 3.205-.012 3.584-.069 4.849-.149 3.225-1.664 4.771-4.919 4.919-1.266.058-1.644.07-4.85.07-3.204 0-3.584-.012-4.849-.07-3.26-.149-4.771-1.699-4.919-4.92-.058-1.265-.07-1.644-.07-4.849 0-3.204.013-3.583.07-4.849.149-3.227 1.664-4.771 4.919-4.919 1.266-.057 1.645-.069 4.849-.069zm0-2.163c-3.259 0-3.667.014-4.947.072-4.358.2-6.78 2.618-6.98 6.98-.059 1.281-.073 1.689-.073 4.948 0 3.259.014 3.668.072 4.948.2 4.358 2.618 6.78 6.98 6.98 1.281.058 1.689.072 4.948.072 3.259 0 3.668-.014 4.948-.072 4.354-.2 6.782-2.618 6.979-6.98.059-1.28.073-1.689.073-4.948 0-3.259-.014-3.667-.072-4.947-.196-4.354-2.617-6.78-6.979-6.98-1.281-.059-1.69-.073-4.949-.073zm0 5.838c-3.403 0-6.162 2.759-6.162 6.162s2.759 6.163 6.162 6.163 6.162-2.759 6.162-6.163c0-3.403-2.759-6.162-6.162-6.162zm0 10.162c-2.209 0-4-1.79-4-4 0-2.209 1.791-4 4-4s4 1.791 4 4c0 2.21-1.791 4-4 4zm6.406-11.845c-.796 0-1.441.645-1.441 1.44s.645 1.44 1.441 1.44c.795 0 1.439-.645 1.439-1.44s-.644-1.44-1.439-1.44z"/>
                    </svg>
                </a>
                <a href="https://x.com/sharvinzlife" target="_blank" class="social-link" title="X (Twitter)">
                    <svg width="24" height="24" viewBox="0 0 24 24" fill="currentColor">
                        <path d="M18.244 2.25h3.308l-7.227 8.26 8.502 11.24H16.17l-5.214-6.817L4.99 21.75H1.68l7.73-8.835L1.254 2.25H8.08l4.713 6.231zm-1.161 17.52h1.833L7.084 4.126H5.117z"/>
                    </svg>
                </a>
            </div>
            <div class="made-with">
                Made with <span class="heart">❤️</span> by 
                <a href="https://github.com/sharvinzlife" target="_blank">Sharvinzlife</a>
                <span class="crown">👑</span>
            </div>
        </div>
    </footer>
'''

DASHBOARD_HTML_6 = '''
    <script>
        async function updateDashboard() {
            try {
                const response = await fetch('/api/status');
                const data = await response.json();
                
                // Update status badge
                const badge = document.getElementById('status-badge');
                const statusText = document.getElementById('status-text');
                if (data.bot_running) {
                    badge.className = 'status-badge status-online';
                    statusText.textContent = 'Online';
                } else {
                    badge.className = 'status-badge status-offline';
                    statusText.textContent = 'Offline';
                }
                
                // Update stats
                document.getElementById('uptime').textContent = data.uptime || '--';
                document.getElementById('messages').textContent = data.total_messages.toLocaleString();
                document.getElementById('tokens').textContent = data.total_tokens.toLocaleString();
                document.getElementById('users').textContent = data.active_users;
                
                // Update providers
                if (data.providers && Object.keys(data.providers).length > 0) {
                    const providersHtml = Object.entries(data.providers).map(([name, info]) => {
                        const icon = name.toLowerCase().includes('groq') ? '⚡' : 
                                    name.toLowerCase().includes('cloud') ? '☁️' : '🖥️';
                        const statusClass = info.status === 'ready' ? 'provider-ready' : 
                                           info.status === 'error' ? 'provider-error' : 'provider-loading';
                        return `<div class="provider-item">
                            <span class="provider-name">${icon} ${name}</span>
                            <span class="provider-status ${statusClass}">${info.status}</span>
                        </div>`;
                    }).join('');
                    document.getElementById('providers').innerHTML = providersHtml;
                }
                
                // Update activity
                if (data.recent_activity && data.recent_activity.length > 0) {
                    const activityHtml = data.recent_activity.slice().reverse().map(item => 
                        `<div class="activity-item">
                            <span class="activity-icon">${item.icon}</span>
                            <span class="activity-text">${item.text}</span>
                            <span class="activity-time">${item.time}</span>
                        </div>`
                    ).join('');
                    document.getElementById('activity').innerHTML = activityHtml;
                }
                
                // Update rate limits
                if (data.rate_limits && Object.keys(data.rate_limits).length > 0) {
                    const ratesHtml = Object.entries(data.rate_limits).map(([name, info]) => {
                        const pct = Math.min(100, (info.current / info.limit) * 100);
                        return `<div class="rate-item">
                            <div class="rate-header">
                                <span>${name}</span>
                                <span>${info.current} / ${info.limit}</span>
                            </div>
                            <div class="rate-bar"><div class="rate-fill" style="width: ${pct}%"></div></div>
                        </div>`;
                    }).join('');
                    document.getElementById('rate-limits').innerHTML = ratesHtml;
                }
            } catch (e) {
                console.error('Dashboard update error:', e);
            }
        }
        
        // Update every 2 seconds
        setInterval(updateDashboard, 2000);
        updateDashboard();
    </script>
</body>
</html>
'''


# Combine all HTML parts
FULL_DASHBOARD_HTML = (
    DASHBOARD_HTML + DASHBOARD_HTML_2 + DASHBOARD_HTML_3 + 
    DASHBOARD_HTML_4 + DASHBOARD_HTML_5 + DASHBOARD_HTML_6
)


def create_dashboard_app(state: Optional[DashboardState] = None) -> Flask:
    """Create Flask app for dashboard."""
    app = Flask(__name__)
    app.config['SECRET_KEY'] = 'openclaw-dashboard-secret'
    
    _state = state or dashboard_state
    
    @app.route('/')
    def index():
        return render_template_string(FULL_DASHBOARD_HTML)
    
    @app.route('/api/status')
    def api_status():
        return jsonify(_state.to_dict())
    
    return app


def run_dashboard(host: str = '0.0.0.0', port: int = 8080, 
                  state: Optional[DashboardState] = None, threaded: bool = True):
    """Run the dashboard server."""
    app = create_dashboard_app(state)
    
    if threaded:
        thread = threading.Thread(
            target=lambda: app.run(host=host, port=port, debug=False, use_reloader=False),
            daemon=True
        )
        thread.start()
        return thread
    else:
        app.run(host=host, port=port, debug=False)


def start_dashboard_thread(host: str = '0.0.0.0', port: int = 8080,
                           state: Optional[DashboardState] = None) -> threading.Thread:
    """Start dashboard in a background thread. Alias for run_dashboard with threaded=True."""
    return run_dashboard(host=host, port=port, state=state, threaded=True)
