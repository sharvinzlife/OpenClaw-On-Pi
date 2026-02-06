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


# HTML Template with Peachy Ivory Glassy Aero Design + Animated Orbs
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
            --peach: #FFDAB9;
            --peach-light: #FFE4C9;
            --peach-dark: #FFCBA4;
            --orange-primary: #FF6B35;
            --orange-light: #FF8C5A;
            --orange-dark: #E55A2B;
            --orange-glow: rgba(255, 107, 53, 0.25);
            --accent-coral: #FF7F50;
            --accent-peach: #FFAB76;
            --accent-amber: #FFB347;
            --text-dark: #2D2D2D;
            --text-medium: #5A5A5A;
            --text-light: #8A8A8A;
            --success: #4CAF50;
            --warning: #FFC107;
            --error: #F44336;
            --glass-bg: rgba(255, 255, 245, 0.75);
            --glass-border: rgba(255, 107, 53, 0.15);
        }
        
        * { margin: 0; padding: 0; box-sizing: border-box; }
        
        body {
            font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
            background: linear-gradient(135deg, var(--ivory) 0%, var(--peach-light) 50%, var(--peach) 100%);
            min-height: 100vh;
            color: var(--text-dark);
            overflow-x: hidden;
        }
        
        /* Animated Floating Orbs - Soft Peachy Colors */
        .orb-container { position: fixed; top: 0; left: 0; width: 100%; height: 100%; pointer-events: none; z-index: 0; overflow: hidden; }
        
        .bg-orb {
            position: absolute;
            border-radius: 50%;
            filter: blur(80px);
            opacity: 0.5;
        }
        .orb-1 { 
            width: 500px; height: 500px; 
            background: radial-gradient(circle, var(--orange-primary) 0%, transparent 70%);
            top: -150px; right: -100px; 
            animation: floatOrb1 25s ease-in-out infinite;
        }
        .orb-2 { 
            width: 400px; height: 400px; 
            background: radial-gradient(circle, var(--accent-amber) 0%, transparent 70%);
            bottom: -100px; left: -100px; 
            animation: floatOrb2 30s ease-in-out infinite;
        }
        .orb-3 { 
            width: 350px; height: 350px; 
            background: radial-gradient(circle, var(--accent-coral) 0%, transparent 70%);
            top: 40%; left: 55%; 
            animation: floatOrb3 20s ease-in-out infinite;
        }
        .orb-4 { 
            width: 280px; height: 280px; 
            background: radial-gradient(circle, var(--peach-dark) 0%, transparent 70%);
            top: 15%; left: 5%; 
            animation: floatOrb4 22s ease-in-out infinite;
        }
        .orb-5 { 
            width: 220px; height: 220px; 
            background: radial-gradient(circle, var(--accent-peach) 0%, transparent 70%);
            bottom: 25%; right: 10%; 
            animation: floatOrb5 18s ease-in-out infinite;
        }
        
        @keyframes floatOrb1 {
            0%, 100% { transform: translate(0, 0) scale(1); opacity: 0.5; }
            25% { transform: translate(-50px, 80px) scale(1.1); opacity: 0.6; }
            50% { transform: translate(30px, 120px) scale(0.95); opacity: 0.45; }
            75% { transform: translate(-30px, 40px) scale(1.05); opacity: 0.55; }
        }
        @keyframes floatOrb2 {
            0%, 100% { transform: translate(0, 0) scale(1); opacity: 0.45; }
            33% { transform: translate(80px, -60px) scale(1.15); opacity: 0.55; }
            66% { transform: translate(40px, -100px) scale(0.9); opacity: 0.4; }
        }
        @keyframes floatOrb3 {
            0%, 100% { transform: translate(0, 0) scale(1); opacity: 0.5; }
            20% { transform: translate(-60px, 40px) scale(1.1); opacity: 0.55; }
            40% { transform: translate(-100px, -30px) scale(0.95); opacity: 0.45; }
            60% { transform: translate(-40px, -80px) scale(1.05); opacity: 0.5; }
            80% { transform: translate(20px, -40px) scale(1); opacity: 0.45; }
        }
        @keyframes floatOrb4 {
            0%, 100% { transform: translate(0, 0) scale(1); opacity: 0.4; }
            50% { transform: translate(100px, 60px) scale(1.2); opacity: 0.5; }
        }
        @keyframes floatOrb5 {
            0%, 100% { transform: translate(0, 0) scale(1); opacity: 0.45; }
            33% { transform: translate(-70px, -50px) scale(1.1); opacity: 0.55; }
            66% { transform: translate(-30px, 40px) scale(0.9); opacity: 0.4; }
        }
        
        /* Glassy Sticky Header - Aero Style */
        .header {
            background: rgba(255, 255, 250, 0.7);
            backdrop-filter: blur(20px);
            -webkit-backdrop-filter: blur(20px);
            border-bottom: 1px solid rgba(255, 107, 53, 0.15);
            padding: 1rem 2rem;
            position: fixed;
            top: 0;
            left: 0;
            right: 0;
            z-index: 1000;
            box-shadow: 0 4px 30px rgba(255, 107, 53, 0.08);
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
            width: 50px; height: 50px;
            background: linear-gradient(135deg, var(--orange-primary), var(--orange-light));
            border-radius: 14px;
            display: flex; align-items: center; justify-content: center;
            font-size: 28px;
            box-shadow: 0 4px 20px var(--orange-glow);
            animation: logoGlow 3s ease-in-out infinite;
        }
        @keyframes logoGlow {
            0%, 100% { box-shadow: 0 4px 20px var(--orange-glow); }
            50% { box-shadow: 0 4px 30px rgba(255, 107, 53, 0.4); }
        }
        .logo-text {
            font-size: 1.6rem; font-weight: 700;
            background: linear-gradient(135deg, var(--orange-dark), var(--orange-primary));
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
        }
        .status-badge {
            display: flex; align-items: center; gap: 8px;
            padding: 10px 20px;
            background: rgba(255, 255, 255, 0.6);
            border: 1px solid rgba(255, 107, 53, 0.2);
            border-radius: 50px;
            font-size: 0.9rem; font-weight: 500;
            color: var(--text-dark);
            backdrop-filter: blur(10px);
        }
        .status-dot {
            width: 12px; height: 12px; border-radius: 50%;
            animation: pulse 2s ease-in-out infinite;
        }
        .status-dot.online { background: var(--success); box-shadow: 0 0 12px var(--success); }
        .status-dot.offline { background: var(--error); box-shadow: 0 0 12px var(--error); }
        @keyframes pulse { 0%, 100% { opacity: 1; transform: scale(1); } 50% { opacity: 0.7; transform: scale(1.1); } }
        
        .main { max-width: 1400px; margin: 0 auto; padding: 100px 2rem 2rem; position: relative; z-index: 1; }
        
        .stats-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(240px, 1fr));
            gap: 1.5rem;
            margin-bottom: 2rem;
        }
        .stat-card {
            background: rgba(255, 255, 255, 0.65);
            backdrop-filter: blur(20px);
            -webkit-backdrop-filter: blur(20px);
            border: 1px solid rgba(255, 107, 53, 0.15);
            border-radius: 20px;
            padding: 1.5rem;
            transition: all 0.4s cubic-bezier(0.175, 0.885, 0.32, 1.275);
            position: relative;
            overflow: hidden;
        }
        .stat-card::before {
            content: '';
            position: absolute;
            top: 0; left: -100%;
            width: 100%; height: 100%;
            background: linear-gradient(90deg, transparent, rgba(255, 255, 255, 0.4), transparent);
            transition: left 0.5s;
        }
        .stat-card:hover::before { left: 100%; }
        .stat-card:hover {
            transform: translateY(-8px) scale(1.02);
            box-shadow: 0 25px 50px rgba(255, 107, 53, 0.15);
            border-color: var(--orange-primary);
            background: rgba(255, 255, 255, 0.8);
        }
        .stat-icon {
            width: 55px; height: 55px;
            background: linear-gradient(135deg, var(--orange-primary), var(--accent-coral));
            border-radius: 16px;
            display: flex; align-items: center; justify-content: center;
            font-size: 26px;
            margin-bottom: 1rem;
            box-shadow: 0 8px 25px var(--orange-glow);
            animation: iconFloat 4s ease-in-out infinite;
        }
        @keyframes iconFloat {
            0%, 100% { transform: translateY(0); }
            50% { transform: translateY(-5px); }
        }
        .stat-label {
            font-size: 0.85rem;
            color: var(--text-light);
            text-transform: uppercase;
            letter-spacing: 1px;
            margin-bottom: 0.5rem;
        }
        .stat-value { font-size: 2.2rem; font-weight: 700; color: var(--text-dark); }
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
            background: rgba(255, 255, 255, 0.6);
            backdrop-filter: blur(20px);
            -webkit-backdrop-filter: blur(20px);
            border: 1px solid rgba(255, 107, 53, 0.12);
            border-radius: 20px;
            overflow: hidden;
            transition: all 0.3s ease;
        }
        .panel:hover {
            border-color: rgba(255, 107, 53, 0.25);
            box-shadow: 0 15px 40px rgba(255, 107, 53, 0.1);
            background: rgba(255, 255, 255, 0.75);
        }
        .panel-header {
            padding: 1.25rem 1.5rem;
            border-bottom: 1px solid rgba(255, 107, 53, 0.1);
            display: flex; align-items: center; gap: 10px;
            background: rgba(255, 255, 255, 0.3);
        }
        .panel-title { font-size: 1.1rem; font-weight: 600; color: var(--text-dark); }
        .panel-content { padding: 1.5rem; }
        
        .provider-list { display: flex; flex-direction: column; gap: 1rem; }
        .provider-card {
            display: flex; align-items: center; justify-content: space-between;
            padding: 1rem 1.25rem;
            background: rgba(255, 255, 255, 0.5);
            border: 1px solid rgba(255, 107, 53, 0.1);
            border-radius: 14px;
            transition: all 0.3s ease;
        }
        .provider-card:hover {
            background: rgba(255, 255, 255, 0.8);
            border-color: var(--orange-light);
            transform: translateX(5px);
        }
        .provider-info { display: flex; align-items: center; gap: 12px; }
        .provider-icon {
            width: 44px; height: 44px; border-radius: 12px;
            display: flex; align-items: center; justify-content: center;
            font-size: 22px;
        }
        .provider-icon.groq { background: linear-gradient(135deg, #6366F1, #8B5CF6); }
        .provider-icon.ollama { background: linear-gradient(135deg, #10B981, #34D399); }
        .provider-icon.local { background: linear-gradient(135deg, #F59E0B, #FBBF24); }
        .provider-name { font-weight: 600; color: var(--text-dark); }
        .provider-status { font-size: 0.8rem; color: var(--text-light); }
        .provider-badge {
            padding: 6px 14px; border-radius: 50px;
            font-size: 0.75rem; font-weight: 600; text-transform: uppercase;
        }
        .provider-badge.healthy { background: rgba(76, 175, 80, 0.15); color: #2E7D32; }
        .provider-badge.unhealthy { background: rgba(244, 67, 54, 0.15); color: #C62828; }
        
        .rate-limit-item { margin-bottom: 1.25rem; }
        .rate-limit-header { display: flex; justify-content: space-between; margin-bottom: 0.5rem; }
        .rate-limit-label { font-size: 0.875rem; font-weight: 500; color: var(--text-dark); }
        .rate-limit-value { font-size: 0.875rem; color: var(--text-light); }
        .rate-limit-bar { height: 10px; background: rgba(0, 0, 0, 0.08); border-radius: 5px; overflow: hidden; }
        .rate-limit-fill { height: 100%; border-radius: 5px; transition: width 0.5s ease; position: relative; }
        .rate-limit-fill::after {
            content: '';
            position: absolute;
            top: 0; left: 0; right: 0; bottom: 0;
            background: linear-gradient(90deg, transparent, rgba(255, 255, 255, 0.4), transparent);
            animation: shimmer 2s infinite;
        }
        @keyframes shimmer { 0% { transform: translateX(-100%); } 100% { transform: translateX(100%); } }
        .rate-limit-fill.low { background: linear-gradient(90deg, #4CAF50, #81C784); }
        .rate-limit-fill.medium { background: linear-gradient(90deg, #FFC107, #FFD54F); }
        .rate-limit-fill.high { background: linear-gradient(90deg, var(--orange-primary), #EF5350); }
        
        .activity-list { display: flex; flex-direction: column; gap: 0.75rem; max-height: 300px; overflow-y: auto; }
        .activity-item {
            display: flex; align-items: flex-start; gap: 12px;
            padding: 0.85rem;
            background: rgba(255, 255, 255, 0.4);
            border-radius: 12px;
            transition: all 0.2s ease;
            animation: slideIn 0.3s ease;
        }
        @keyframes slideIn { from { opacity: 0; transform: translateX(-10px); } to { opacity: 1; transform: translateX(0); } }
        .activity-item:hover { background: rgba(255, 255, 255, 0.7); }
        .activity-icon {
            width: 36px; height: 36px; border-radius: 10px;
            display: flex; align-items: center; justify-content: center;
            font-size: 16px; flex-shrink: 0;
        }
        .activity-icon.message { background: rgba(255, 107, 53, 0.2); }
        .activity-icon.command { background: rgba(99, 102, 241, 0.2); }
        .activity-icon.error { background: rgba(244, 67, 54, 0.2); }
        .activity-content { flex: 1; min-width: 0; }
        .activity-text { font-size: 0.875rem; color: var(--text-dark); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
        .activity-time { font-size: 0.75rem; color: var(--text-light); }
        
        .empty-state { text-align: center; padding: 2rem; color: var(--text-light); }
        .empty-state-icon { font-size: 3rem; margin-bottom: 1rem; opacity: 0.5; animation: bounce 2s ease-in-out infinite; }
        @keyframes bounce { 0%, 100% { transform: translateY(0); } 50% { transform: translateY(-10px); } }
        
        /* Glassy Sticky Footer - Aero Style */
        .footer {
            text-align: center; padding: 2rem;
            background: rgba(255, 255, 250, 0.75);
            backdrop-filter: blur(20px);
            -webkit-backdrop-filter: blur(20px);
            border-top: 1px solid rgba(255, 107, 53, 0.15);
            margin-top: 2rem;
            position: relative;
            z-index: 100;
        }
        .social-links {
            display: flex; justify-content: center; gap: 1.5rem; margin-bottom: 1.25rem;
        }
        .social-link {
            width: 50px; height: 50px; border-radius: 50%;
            background: linear-gradient(135deg, #FFD700, #FFA500);
            display: flex; align-items: center; justify-content: center;
            color: white; text-decoration: none;
            box-shadow: 0 4px 20px rgba(255, 215, 0, 0.35);
            transition: all 0.4s cubic-bezier(0.175, 0.885, 0.32, 1.275);
            position: relative;
        }
        .social-link::before {
            content: '';
            position: absolute;
            inset: -3px;
            border-radius: 50%;
            background: linear-gradient(135deg, #FFD700, #FFA500, #FF6B35);
            z-index: -1;
            opacity: 0;
            transition: opacity 0.3s;
        }
        .social-link:hover::before { opacity: 1; animation: spin 3s linear infinite; }
        @keyframes spin { from { transform: rotate(0deg); } to { transform: rotate(360deg); } }
        .social-link:hover {
            transform: translateY(-8px) scale(1.15);
            box-shadow: 0 15px 35px rgba(255, 215, 0, 0.45);
        }
        .social-link svg { width: 24px; height: 24px; fill: white; }
        .made-with {
            display: flex; align-items: center; justify-content: center; gap: 0.5rem;
            color: var(--text-medium); font-size: 1rem;
        }
        .made-with .heart { color: #ef4444; animation: heartbeat 1.5s ease-in-out infinite; }
        .made-with .crown { color: #FFD700; animation: shine 2s ease-in-out infinite; }
        .made-with a { 
            color: var(--orange-primary); text-decoration: none; font-weight: 600;
            transition: all 0.3s;
        }
        .made-with a:hover { color: var(--orange-dark); }
        @keyframes heartbeat { 0%, 100% { transform: scale(1); } 50% { transform: scale(1.3); } }
        @keyframes shine { 0%, 100% { filter: brightness(1) drop-shadow(0 0 3px #FFD700); } 50% { filter: brightness(1.3) drop-shadow(0 0 10px #FFD700); } }
        
        @media (max-width: 768px) {
            .header-content { flex-direction: column; gap: 1rem; }
            .panels { grid-template-columns: 1fr; }
            .main { padding: 90px 1rem 1rem; }
        }
        ::-webkit-scrollbar { width: 8px; }
        ::-webkit-scrollbar-track { background: rgba(255, 255, 255, 0.3); border-radius: 4px; }
        ::-webkit-scrollbar-thumb { background: var(--orange-primary); border-radius: 4px; }
        ::-webkit-scrollbar-thumb:hover { background: var(--orange-dark); }
    </style>
</head>
<body>
    <div class="orb-container">
        <div class="bg-orb orb-1"></div>
        <div class="bg-orb orb-2"></div>
        <div class="bg-orb orb-3"></div>
        <div class="bg-orb orb-4"></div>
        <div class="bg-orb orb-5"></div>
    </div>
    
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
                
                // Update rate limits dynamically
                if (data.rate_limits) {
                    const rateLimitsEl = document.getElementById('rateLimits');
                    let rateLimitsHtml = '';
                    
                    // Groq RPM
                    const rpm = data.rate_limits.groq_rpm || {current: 0, limit: 30};
                    const rpmPercent = rpm.limit > 0 ? (rpm.current / rpm.limit) * 100 : 0;
                    const rpmClass = rpmPercent > 80 ? 'high' : rpmPercent > 50 ? 'medium' : 'low';
                    rateLimitsHtml += `
                        <div class="rate-limit-item">
                            <div class="rate-limit-header">
                                <span class="rate-limit-label">Groq RPM</span>
                                <span class="rate-limit-value">${rpm.current} / ${rpm.limit}</span>
                            </div>
                            <div class="rate-limit-bar">
                                <div class="rate-limit-fill ${rpmClass}" style="width: ${Math.min(rpmPercent, 100)}%"></div>
                            </div>
                        </div>
                    `;
                    
                    // Groq TPM
                    const tpm = data.rate_limits.groq_tpm || {current: 0, limit: 14400};
                    const tpmPercent = tpm.limit > 0 ? (tpm.current / tpm.limit) * 100 : 0;
                    const tpmClass = tpmPercent > 80 ? 'high' : tpmPercent > 50 ? 'medium' : 'low';
                    rateLimitsHtml += `
                        <div class="rate-limit-item">
                            <div class="rate-limit-header">
                                <span class="rate-limit-label">Groq TPM</span>
                                <span class="rate-limit-value">${tpm.current.toLocaleString()} / ${tpm.limit.toLocaleString()}</span>
                            </div>
                            <div class="rate-limit-bar">
                                <div class="rate-limit-fill ${tpmClass}" style="width: ${Math.min(tpmPercent, 100)}%"></div>
                            </div>
                        </div>
                    `;
                    
                    rateLimitsEl.innerHTML = rateLimitsHtml;
                }
                
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
