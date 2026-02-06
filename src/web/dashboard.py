"""Web dashboard for OpenClaw bot monitoring."""

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
        """Add activity to recent list."""
        self.recent_activity.append({
            "type": activity_type,
            "text": text,
            "icon": icon,
            "time": datetime.now().strftime("%H:%M:%S"),
        })
        if len(self.recent_activity) > 50:
            self.recent_activity = self.recent_activity[-50:]


# Global state
dashboard_state = DashboardState()


# HTML Template with Glassy Ivory-Orange Design
DASHBOARD_HTML = '''
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>OpenClaw Dashboard</title>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap" rel="stylesheet">
    <style>
        :root {
            --ivory: #FFFFF0;
            --ivory-light: #FFFEF5;
            --ivory-dark: #F5F5DC;
            --orange-primary: #FF6B35;
            --orange-light: #FF8C5A;
            --orange-dark: #E55A2B;
            --orange-glow: rgba(255, 107, 53, 0.3);
            --accent-coral: #FF7F50;
            --accent-peach: #FFAB76;
            --accent-amber: #FFB347;
            --text-dark: #2D2D2D;
            --text-medium: #5A5A5A;
            --text-light: #8A8A8A;
            --success: #4CAF50;
            --warning: #FFC107;
            --error: #F44336;
            --glass-bg: rgba(255, 255, 240, 0.7);
            --glass-border: rgba(255, 107, 53, 0.2);
        }
        
        * { margin: 0; padding: 0; box-sizing: border-box; }
        
        body {
            font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
            background: linear-gradient(135deg, var(--ivory) 0%, var(--ivory-dark) 50%, var(--accent-peach) 100%);
            min-height: 100vh;
            color: var(--text-dark);
            overflow-x: hidden;
        }
        
        .bg-orb {
            position: fixed;
            border-radius: 50%;
            filter: blur(80px);
            opacity: 0.5;
            z-index: -1;
            animation: float 20s ease-in-out infinite;
        }
        .orb-1 { width: 400px; height: 400px; background: var(--orange-primary); top: -100px; right: -100px; }
        .orb-2 { width: 300px; height: 300px; background: var(--accent-amber); bottom: -50px; left: -50px; animation-delay: -5s; }
        .orb-3 { width: 200px; height: 200px; background: var(--accent-coral); top: 50%; left: 50%; animation-delay: -10s; }
        
        @keyframes float {
            0%, 100% { transform: translate(0, 0) scale(1); }
            25% { transform: translate(30px, -30px) scale(1.1); }
            50% { transform: translate(-20px, 20px) scale(0.9); }
            75% { transform: translate(20px, 30px) scale(1.05); }
        }
        
        .header {
            background: var(--glass-bg);
            backdrop-filter: blur(20px);
            border-bottom: 1px solid var(--glass-border);
            padding: 1rem 2rem;
            position: sticky;
            top: 0;
            z-index: 100;
        }
        .header-content {
            max-width: 1400px;
            margin: 0 auto;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }
        .logo { display: flex; align-items: center; gap: 12px; }
        .logo-icon {
            width: 45px; height: 45px;
            background: linear-gradient(135deg, var(--orange-primary), var(--orange-light));
            border-radius: 12px;
            display: flex; align-items: center; justify-content: center;
            font-size: 24px;
            box-shadow: 0 4px 15px var(--orange-glow);
        }
        .logo-text {
            font-size: 1.5rem; font-weight: 700;
            background: linear-gradient(135deg, var(--orange-dark), var(--orange-primary));
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
        }
        .status-badge {
            display: flex; align-items: center; gap: 8px;
            padding: 8px 16px;
            background: var(--glass-bg);
            border: 1px solid var(--glass-border);
            border-radius: 50px;
            font-size: 0.875rem; font-weight: 500;
        }
        .status-dot {
            width: 10px; height: 10px; border-radius: 50%;
            animation: pulse 2s ease-in-out infinite;
        }
        .status-dot.online { background: var(--success); box-shadow: 0 0 10px var(--success); }
        .status-dot.offline { background: var(--error); box-shadow: 0 0 10px var(--error); }
        @keyframes pulse { 0%, 100% { opacity: 1; } 50% { opacity: 0.7; } }
        
        .main { max-width: 1400px; margin: 0 auto; padding: 2rem; }
        
        .stats-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(240px, 1fr));
            gap: 1.5rem;
            margin-bottom: 2rem;
        }
        .stat-card {
            background: var(--glass-bg);
            backdrop-filter: blur(20px);
            border: 1px solid var(--glass-border);
            border-radius: 20px;
            padding: 1.5rem;
            transition: all 0.3s ease;
        }
        .stat-card:hover {
            transform: translateY(-5px);
            box-shadow: 0 20px 40px rgba(255, 107, 53, 0.15);
            border-color: var(--orange-primary);
        }
        .stat-icon {
            width: 50px; height: 50px;
            background: linear-gradient(135deg, var(--orange-primary), var(--accent-coral));
            border-radius: 14px;
            display: flex; align-items: center; justify-content: center;
            font-size: 24px;
            margin-bottom: 1rem;
            box-shadow: 0 4px 15px var(--orange-glow);
        }
        .stat-label {
            font-size: 0.875rem;
            color: var(--text-light);
            text-transform: uppercase;
            letter-spacing: 0.5px;
            margin-bottom: 0.5rem;
        }
        .stat-value { font-size: 2rem; font-weight: 700; color: var(--text-dark); }
        .stat-value.highlight {
            background: linear-gradient(135deg, var(--orange-dark), var(--orange-primary));
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
        }
        
        .panels {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(400px, 1fr));
            gap: 1.5rem;
        }
        .panel {
            background: var(--glass-bg);
            backdrop-filter: blur(20px);
            border: 1px solid var(--glass-border);
            border-radius: 20px;
            overflow: hidden;
        }
        .panel-header {
            padding: 1.25rem 1.5rem;
            border-bottom: 1px solid var(--glass-border);
            display: flex; align-items: center; gap: 10px;
        }
        .panel-title { font-size: 1.1rem; font-weight: 600; color: var(--text-dark); }
        .panel-content { padding: 1.5rem; }
        
        .provider-list { display: flex; flex-direction: column; gap: 1rem; }
        .provider-card {
            display: flex; align-items: center; justify-content: space-between;
            padding: 1rem 1.25rem;
            background: rgba(255, 255, 255, 0.5);
            border: 1px solid var(--glass-border);
            border-radius: 14px;
            transition: all 0.2s ease;
        }
        .provider-card:hover {
            background: rgba(255, 255, 255, 0.8);
            border-color: var(--orange-light);
        }
        .provider-info { display: flex; align-items: center; gap: 12px; }
        .provider-icon {
            width: 40px; height: 40px; border-radius: 10px;
            display: flex; align-items: center; justify-content: center;
            font-size: 20px;
        }
        .provider-icon.groq { background: linear-gradient(135deg, #6366F1, #8B5CF6); }
        .provider-icon.ollama { background: linear-gradient(135deg, #10B981, #34D399); }
        .provider-icon.local { background: linear-gradient(135deg, #F59E0B, #FBBF24); }
        .provider-name { font-weight: 600; color: var(--text-dark); }
        .provider-status { font-size: 0.8rem; color: var(--text-light); }
        .provider-badge {
            padding: 6px 12px; border-radius: 50px;
            font-size: 0.75rem; font-weight: 600; text-transform: uppercase;
        }
        .provider-badge.healthy { background: rgba(76, 175, 80, 0.15); color: var(--success); }
        .provider-badge.unhealthy { background: rgba(244, 67, 54, 0.15); color: var(--error); }
        
        .rate-limit-item { margin-bottom: 1.25rem; }
        .rate-limit-header { display: flex; justify-content: space-between; margin-bottom: 0.5rem; }
        .rate-limit-label { font-size: 0.875rem; font-weight: 500; color: var(--text-dark); }
        .rate-limit-value { font-size: 0.875rem; color: var(--text-light); }
        .rate-limit-bar { height: 8px; background: rgba(0, 0, 0, 0.1); border-radius: 4px; overflow: hidden; }
        .rate-limit-fill { height: 100%; border-radius: 4px; transition: width 0.5s ease; }
        .rate-limit-fill.low { background: linear-gradient(90deg, var(--success), #81C784); }
        .rate-limit-fill.medium { background: linear-gradient(90deg, var(--warning), #FFD54F); }
        .rate-limit-fill.high { background: linear-gradient(90deg, var(--orange-primary), var(--error)); }
        
        .activity-list { display: flex; flex-direction: column; gap: 0.75rem; max-height: 300px; overflow-y: auto; }
        .activity-item {
            display: flex; align-items: flex-start; gap: 12px;
            padding: 0.75rem;
            background: rgba(255, 255, 255, 0.3);
            border-radius: 10px;
        }
        .activity-icon {
            width: 32px; height: 32px; border-radius: 8px;
            display: flex; align-items: center; justify-content: center;
            font-size: 14px; flex-shrink: 0;
        }
        .activity-icon.message { background: rgba(255, 107, 53, 0.2); }
        .activity-icon.command { background: rgba(99, 102, 241, 0.2); }
        .activity-icon.error { background: rgba(244, 67, 54, 0.2); }
        .activity-content { flex: 1; min-width: 0; }
        .activity-text { font-size: 0.875rem; color: var(--text-dark); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
        .activity-time { font-size: 0.75rem; color: var(--text-light); }
        
        .empty-state { text-align: center; padding: 2rem; color: var(--text-light); }
        .empty-state-icon { font-size: 3rem; margin-bottom: 1rem; opacity: 0.5; }
        
        .footer {
            text-align: center; padding: 2rem;
            background: var(--glass-bg);
            backdrop-filter: blur(20px);
            border-top: 1px solid var(--glass-border);
            margin-top: 2rem;
        }
        .social-links {
            display: flex; justify-content: center; gap: 1.5rem; margin-bottom: 1rem;
        }
        .social-link {
            width: 45px; height: 45px; border-radius: 50%;
            background: linear-gradient(135deg, #FFD700, #FFA500);
            display: flex; align-items: center; justify-content: center;
            color: white; text-decoration: none;
            box-shadow: 0 4px 15px rgba(255, 215, 0, 0.4);
            transition: all 0.3s cubic-bezier(0.175, 0.885, 0.32, 1.275);
        }
        .social-link:hover {
            transform: translateY(-5px) scale(1.1);
            box-shadow: 0 10px 25px rgba(255, 215, 0, 0.6);
        }
        .social-link svg { width: 22px; height: 22px; fill: white; }
        .made-with {
            display: flex; align-items: center; justify-content: center; gap: 0.5rem;
            color: var(--text-medium); font-size: 0.95rem;
        }
        .made-with .heart { color: #ef4444; animation: heartbeat 1.5s ease-in-out infinite; }
        .made-with .crown { color: #FFD700; animation: shine 2s ease-in-out infinite; }
        .made-with a { color: var(--orange-primary); text-decoration: none; font-weight: 600; }
        .made-with a:hover { color: var(--orange-dark); }
        @keyframes heartbeat { 0%, 100% { transform: scale(1); } 50% { transform: scale(1.2); } }
        @keyframes shine { 0%, 100% { filter: brightness(1); } 50% { filter: brightness(1.3); } }
        
        @media (max-width: 768px) {
            .header-content { flex-direction: column; gap: 1rem; }
            .panels { grid-template-columns: 1fr; }
            .main { padding: 1rem; }
        }
        ::-webkit-scrollbar { width: 6px; }
        ::-webkit-scrollbar-track { background: transparent; }
        ::-webkit-scrollbar-thumb { background: var(--orange-light); border-radius: 3px; }
    </style>
</head>
<body>
    <div class="bg-orb orb-1"></div>
    <div class="bg-orb orb-2"></div>
    <div class="bg-orb orb-3"></div>
    
    <header class="header">
        <div class="header-content">
            <div class="logo">
                <div class="logo-icon">🦞</div>
                <span class="logo-text">OpenClaw</span>
            </div>
            <div class="status-badge">
                <span class="status-dot" id="statusDot"></span>
                <span id="statusText">Checking...</span>
            </div>
        </div>
    </header>
    
    <main class="main">
        <div class="stats-grid">
            <div class="stat-card">
                <div class="stat-icon">⏱️</div>
                <div class="stat-label">Uptime</div>
                <div class="stat-value highlight" id="uptime">--</div>
            </div>
            <div class="stat-card">
                <div class="stat-icon">💬</div>
                <div class="stat-label">Messages</div>
                <div class="stat-value" id="messages">0</div>
            </div>
            <div class="stat-card">
                <div class="stat-icon">🎯</div>
                <div class="stat-label">Tokens Used</div>
                <div class="stat-value" id="tokens">0</div>
            </div>
            <div class="stat-card">
                <div class="stat-icon">👥</div>
                <div class="stat-label">Active Users</div>
                <div class="stat-value" id="users">0</div>
            </div>
        </div>
        
        <div class="panels">
            <div class="panel">
                <div class="panel-header">
                    <span>🧠</span>
                    <span class="panel-title">AI Providers</span>
                </div>
                <div class="panel-content">
                    <div class="provider-list" id="providerList">
                        <div class="provider-card">
                            <div class="provider-info">
                                <div class="provider-icon groq">⚡</div>
                                <div>
                                    <div class="provider-name">Groq</div>
                                    <div class="provider-status">Primary • Fast inference</div>
                                </div>
                            </div>
                            <span class="provider-badge healthy">Ready</span>
                        </div>
                        <div class="provider-card">
                            <div class="provider-info">
                                <div class="provider-icon ollama">☁️</div>
                                <div>
                                    <div class="provider-name">Ollama Cloud</div>
                                    <div class="provider-status">Backup • Remote</div>
                                </div>
                            </div>
                            <span class="provider-badge healthy">Ready</span>
                        </div>
                        <div class="provider-card">
                            <div class="provider-info">
                                <div class="provider-icon local">🖥️</div>
                                <div>
                                    <div class="provider-name">Local Ollama</div>
                                    <div class="provider-status">Fallback • Privacy</div>
                                </div>
                            </div>
                            <span class="provider-badge unhealthy">Disabled</span>
                        </div>
                    </div>
                </div>
            </div>
            
            <div class="panel">
                <div class="panel-header">
                    <span>📊</span>
                    <span class="panel-title">Rate Limits</span>
                </div>
                <div class="panel-content" id="rateLimits">
                    <div class="rate-limit-item">
                        <div class="rate-limit-header">
                            <span class="rate-limit-label">Groq RPM</span>
                            <span class="rate-limit-value">0 / 30</span>
                        </div>
                        <div class="rate-limit-bar">
                            <div class="rate-limit-fill low" style="width: 0%"></div>
                        </div>
                    </div>
                    <div class="rate-limit-item">
                        <div class="rate-limit-header">
                            <span class="rate-limit-label">Groq TPM</span>
                            <span class="rate-limit-value">0 / 14,400</span>
                        </div>
                        <div class="rate-limit-bar">
                            <div class="rate-limit-fill low" style="width: 0%"></div>
                        </div>
                    </div>
                </div>
            </div>
            
            <div class="panel">
                <div class="panel-header">
                    <span>📝</span>
                    <span class="panel-title">Recent Activity</span>
                </div>
                <div class="panel-content">
                    <div class="activity-list" id="activityList">
                        <div class="empty-state">
                            <div class="empty-state-icon">💤</div>
                            <div>No activity yet</div>
                        </div>
                    </div>
                </div>
            </div>
            
            <div class="panel">
                <div class="panel-header">
                    <span>🖥️</span>
                    <span class="panel-title">System</span>
                </div>
                <div class="panel-content">
                    <div class="provider-list">
                        <div class="provider-card">
                            <div class="provider-info">
                                <div class="provider-icon local">🍓</div>
                                <div>
                                    <div class="provider-name">Raspberry Pi</div>
                                    <div class="provider-status">DietPi • ARM64</div>
                                </div>
                            </div>
                        </div>
                        <div class="provider-card">
                            <div class="provider-info">
                                <div class="provider-icon groq">🐍</div>
                                <div>
                                    <div class="provider-name">Python</div>
                                    <div class="provider-status">3.9+</div>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    </main>
    
    <footer class="footer">
        <div class="social-links">
            <a href="https://fb.com/sharvinzlife" target="_blank" class="social-link" title="Facebook">
                <svg viewBox="0 0 24 24"><path d="M24 12.073c0-6.627-5.373-12-12-12s-12 5.373-12 12c0 5.99 4.388 10.954 10.125 11.854v-8.385H7.078v-3.47h3.047V9.43c0-3.007 1.792-4.669 4.533-4.669 1.312 0 2.686.235 2.686.235v2.953H15.83c-1.491 0-1.956.925-1.956 1.874v2.25h3.328l-.532 3.47h-2.796v8.385C19.612 23.027 24 18.062 24 12.073z"/></svg>
            </a>
            <a href="https://instagram.com/sharvinzlife" target="_blank" class="social-link" title="Instagram">
                <svg viewBox="0 0 24 24"><path d="M12 2.163c3.204 0 3.584.012 4.85.07 3.252.148 4.771 1.691 4.919 4.919.058 1.265.069 1.645.069 4.849 0 3.205-.012 3.584-.069 4.849-.149 3.225-1.664 4.771-4.919 4.919-1.266.058-1.644.07-4.85.07-3.204 0-3.584-.012-4.849-.07-3.26-.149-4.771-1.699-4.919-4.92-.058-1.265-.07-1.644-.07-4.849 0-3.204.013-3.583.07-4.849.149-3.227 1.664-4.771 4.919-4.919 1.266-.057 1.645-.069 4.849-.069zm0-2.163c-3.259 0-3.667.014-4.947.072-4.358.2-6.78 2.618-6.98 6.98-.059 1.281-.073 1.689-.073 4.948 0 3.259.014 3.668.072 4.948.2 4.358 2.618 6.78 6.98 6.98 1.281.058 1.689.072 4.948.072 3.259 0 3.668-.014 4.948-.072 4.354-.2 6.782-2.618 6.979-6.98.059-1.28.073-1.689.073-4.948 0-3.259-.014-3.667-.072-4.947-.196-4.354-2.617-6.78-6.979-6.98-1.281-.059-1.69-.073-4.949-.073zm0 5.838c-3.403 0-6.162 2.759-6.162 6.162s2.759 6.163 6.162 6.163 6.162-2.759 6.162-6.163c0-3.403-2.759-6.162-6.162-6.162zm0 10.162c-2.209 0-4-1.79-4-4 0-2.209 1.791-4 4-4s4 1.791 4 4c0 2.21-1.791 4-4 4zm6.406-11.845c-.796 0-1.441.645-1.441 1.44s.645 1.44 1.441 1.44c.795 0 1.439-.645 1.439-1.44s-.644-1.44-1.439-1.44z"/></svg>
            </a>
            <a href="https://x.com/sharvinzlife" target="_blank" class="social-link" title="X (Twitter)">
                <svg viewBox="0 0 24 24"><path d="M18.244 2.25h3.308l-7.227 8.26 8.502 11.24H16.17l-5.214-6.817L4.99 21.75H1.68l7.73-8.835L1.254 2.25H8.08l4.713 6.231zm-1.161 17.52h1.833L7.084 4.126H5.117z"/></svg>
            </a>
        </div>
        <div class="made-with">
            Made with <span class="heart">❤️</span> by 
            <a href="https://github.com/sharvinzlife" target="_blank">Sharvinzlife</a>
            <span class="crown">👑</span>
        </div>
    </footer>
    
    <script>
        async function updateDashboard() {
            try {
                const response = await fetch('/api/status');
                const data = await response.json();
                
                const statusDot = document.getElementById('statusDot');
                const statusText = document.getElementById('statusText');
                if (data.bot_running) {
                    statusDot.className = 'status-dot online';
                    statusText.textContent = 'Online';
                } else {
                    statusDot.className = 'status-dot offline';
                    statusText.textContent = 'Offline';
                }
                
                document.getElementById('uptime').textContent = data.uptime || '--';
                document.getElementById('messages').textContent = data.total_messages.toLocaleString();
                document.getElementById('tokens').textContent = data.total_tokens.toLocaleString();
                document.getElementById('users').textContent = data.active_users;
                
                if (data.recent_activity && data.recent_activity.length > 0) {
                    const activityList = document.getElementById('activityList');
                    activityList.innerHTML = data.recent_activity.map(item => `
                        <div class="activity-item">
                            <div class="activity-icon ${item.type}">${item.icon || '💬'}</div>
                            <div class="activity-content">
                                <div class="activity-text">${item.text}</div>
                                <div class="activity-time">${item.time}</div>
                            </div>
                        </div>
                    `).join('');
                }
            } catch (error) {
                console.error('Failed to update dashboard:', error);
            }
        }
        
        updateDashboard();
        setInterval(updateDashboard, 5000);
    </script>
</body>
</html>
'''


def create_dashboard_app(state: Optional[DashboardState] = None) -> Flask:
    """Create Flask dashboard app."""
    global dashboard_state
    if state:
        dashboard_state = state
    
    app = Flask(__name__)
    
    @app.route('/')
    def index():
        return render_template_string(DASHBOARD_HTML)
    
    @app.route('/api/status')
    def api_status():
        return jsonify(dashboard_state.to_dict())
    
    return app


def run_dashboard(host: str = '0.0.0.0', port: int = 8080, state: Optional[DashboardState] = None):
    """Run the dashboard server."""
    app = create_dashboard_app(state)
    app.run(host=host, port=port, debug=False, threaded=True)


def start_dashboard_thread(host: str = '0.0.0.0', port: int = 8080, state: Optional[DashboardState] = None) -> threading.Thread:
    """Start dashboard in a background thread."""
    global dashboard_state
    if state:
        dashboard_state = state
    
    thread = threading.Thread(
        target=run_dashboard,
        kwargs={'host': host, 'port': port, 'state': state},
        daemon=True
    )
    thread.start()
    return thread
