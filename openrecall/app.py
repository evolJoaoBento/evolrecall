import argparse
import os
import sys
from threading import Thread
import json
import markdown

import numpy as np
from flask import Flask, render_template_string, request, send_from_directory, jsonify
from jinja2 import BaseLoader
from datetime import datetime

from openrecall.recording_controller import recording_controller

recording_state = {
    'is_recording': True,
    'is_paused': False,
    'start_time': None
}

# Import after potential config changes
def setup_config(storage_path=None):
    """Setup configuration with optional custom storage path"""
    if storage_path:
        # If custom storage path is provided, we need to update the config
        import openrecall.config as config
        
        # Expand user path if needed (e.g., ~/data becomes /home/user/data)
        storage_path = os.path.expanduser(storage_path)
        
        # Update config values
        config.appdata_folder = storage_path
        config.screenshots_path = os.path.join(storage_path, 'screenshots')
        
        # Update database path if it exists in config
        if hasattr(config, 'database_path'):
            config.database_path = os.path.join(storage_path, 'recall.db')
        
        # Ensure directories exist
        os.makedirs(config.screenshots_path, exist_ok=True)
        os.makedirs(storage_path, exist_ok=True)
        
        print(f"Custom storage path configured: {storage_path}")
        return config.appdata_folder, config.screenshots_path
    else:
        # Use default configuration
        from openrecall.config import appdata_folder, screenshots_path
        return appdata_folder, screenshots_path

# Import these after config is set up
from openrecall.database import create_db, get_all_entries, get_timestamps
from openrecall.nlp import cosine_similarity, get_embedding
from openrecall.screenshot import record_screenshots_thread
from openrecall.utils import human_readable_time, timestamp_to_human_readable

def parse_arguments():
    """Parse command line arguments"""
    parser = argparse.ArgumentParser(description='OpenRecall Web Interface')
    parser.add_argument('--storage-path', 
                       help='Path where screenshots and database should be stored')
    parser.add_argument('--port', type=int, default=8082,
                       help='Port to run the web interface on (default: 8082)')
    parser.add_argument('--host', default='127.0.0.1',
                       help='Host to bind the web interface to (default: 127.0.0.1)')
    return parser.parse_args()


# Parse arguments early
args = parse_arguments()

# Setup configuration based on arguments
appdata_folder, screenshots_path = setup_config(args.storage_path)

# Create Flask app after config is set up
app = Flask(__name__)

app.jinja_env.filters["human_readable_time"] = human_readable_time
app.jinja_env.filters["timestamp_to_human_readable"] = timestamp_to_human_readable

base_template = """
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>OpenRecall</title>
  <!-- Bootstrap CSS -->
  <link href="https://stackpath.bootstrapcdn.com/bootstrap/4.5.2/css/bootstrap.min.css" rel="stylesheet">
  <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/bootstrap-icons@1.3.0/font/bootstrap-icons.css">
  <style>
  * {
    margin: 0;
    padding: 0;
    box-sizing: border-box;
        font-style: normal;
}

.bi-chevron-left::before,
.bi-chevron-right::before,
.bi-arrow-clockwise::before {
    display: none;
}

.markdown-btn:hover {
  background: #f8f9fa;
}

.copy-btn {
  position: absolute;
  top: 10px;
  right: 10px; /* Keep copy button on the far right */
  background: #fff;
  border: 1px solid #dee2e6;
  border-radius: 4px;
  padding: 3px 8px;
  font-size: 0.8em;
  cursor: pointer;
  z-index: 10;
}

.copy-btn:hover {
  background: #f8f9fa;
}

/* Make sure buttons don't overlap on mobile */
@media (max-width: 768px) {
  .markdown-btn {
    top: 10px;
    right: 10px;
  }
  
  .copy-btn {
    top: 45px; /* Stack vertically on mobile */
    right: 10px;
  }
}

.markdown-view {
  background: white;
  padding: 15px;
  border-radius: 4px;
  border: 1px solid #e9ecef;
  max-height: 400px;
  overflow-y: auto;
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
  font-size: 0.95em;
  line-height: 1.6;
}

.markdown-view h1, .markdown-view h2, .markdown-view h3 {
  color: #495057;
  margin-top: 1em;
  margin-bottom: 0.5em;
}

.markdown-view code {
  background: #f8f9fa;
  padding: 2px 4px;
  border-radius: 3px;
  font-size: 0.9em;
}

.markdown-view pre {
  background: #f8f9fa;
  padding: 10px;
  border-radius: 4px;
  overflow-x: auto;
}

.markdown-view blockquote {
  border-left: 4px solid #007bff;
  margin: 1em 0;
  padding-left: 1em;
  color: #6c757d;
}

.markdown-view ul, .markdown-view ol {
  padding-left: 2em;
}

.text-view-toggle {
  display: flex;
  gap: 5px;
  margin-bottom: 10px;
}

.view-mode-btn {
  padding: 4px 12px;
  border: 1px solid #dee2e6;
  background: #f8f9fa;
  border-radius: 4px;
  font-size: 0.85em;
  cursor: pointer;
  transition: all 0.2s;
}

.view-mode-btn.active {
  background: #007bff;
  color: white;
  border-color: #007bff;
}

.view-mode-btn:hover:not(.active) {
  background: #e9ecef;
}

    .timeline-container {
      padding: 20px;
      background: #f8f9fa;
      border-radius: 12px;
      margin: 20px 0;
      box-shadow: 0 2px 10px rgba(0,0,0,0.1);
    }
    
    .timeline-wrapper {
      position: relative;
      height: 80px;
      overflow: hidden;
      border-radius: 8px;
      background: white;
      border: 2px solid #dee2e6;
      cursor: grab;
    }
    
    .timeline-wrapper:active {
      cursor: grabbing;
    }
    
    .timeline-track {
      position: absolute;
      height: 100%;
      display: flex;
      align-items: center;
      transition: transform 0.3s cubic-bezier(0.25, 0.46, 0.45, 0.94);
      cursor: grab;
    }
    
    .timeline-track:active {
      cursor: grabbing;
    }
    
    .timeline-segment {
      height: 40px;
      min-width: 8px;
      margin: 0 1px;
      border-radius: 4px;
      cursor: pointer;
      transition: all 0.2s ease;
      position: relative;
      border: 2px solid transparent;
    }
    
    .timeline-segment:hover {
      transform: scaleY(1.2);
      border-color: #007bff;
      z-index: 10;
    }
    
    .timeline-segment.active {
      transform: scaleY(1.4);
      border-color: #28a745;
      box-shadow: 0 0 10px rgba(40, 167, 69, 0.5);
      z-index: 20;
    }
    
    .timeline-info {
      display: flex;
      justify-content: space-between;
      align-items: center;
      margin-bottom: 15px;
    }
    
    .timeline-controls {
      display: flex;
      gap: 10px;
      align-items: center;
    }
    
    .timeline-nav-btn {
      background: #007bff;
      color: white;
      border: none;
      border-radius: 50%;
      width: 40px;
      height: 40px;
      cursor: pointer;
      display: flex;
      align-items: center;
      justify-content: center;
      transition: all 0.2s ease;
    }
    
    .timeline-nav-btn:hover {
      background: #0056b3;
      transform: scale(1.1);
    }
    
    .timeline-nav-btn:disabled {
      background: #6c757d;
      cursor: not-allowed;
      transform: none;
    }
    
    .app-legend {
      display: flex;
      flex-wrap: wrap;
      gap: 8px;
      margin-top: 15px;
    }
    
    .app-legend-item {
      display: flex;
      align-items: center;
      gap: 5px;
      padding: 4px 8px;
      background: white;
      border-radius: 4px;
      font-size: 0.85em;
      border: 1px solid #dee2e6;
    }
    
    .app-color-dot {
      width: 12px;
      height: 12px;
      border-radius: 50%;
    }
    
    .timeline-position-indicator {
      position: absolute;
      top: 0;
      bottom: 0;
      width: 3px;
      background: #28a745;
      border-radius: 2px;
      box-shadow: 0 0 5px rgba(40, 167, 69, 0.7);
      z-index: 30;
      transition: left 0.3s ease;
    }
    
    .content-container {
      margin-top: 20px;
    }
    
    .image-container {
      text-align: center;
      margin-bottom: 20px;
      position: relative;
    }
    
    .image-container img {
      max-width: 100%;
      height: auto;
      border: 1px solid #ddd;
      border-radius: 8px;
      transition: opacity 0.3s ease;
    }
    
    .image-loading {
      opacity: 0.7;
    }
    
    .entry-info {
      background: white;
      padding: 20px;
      border-radius: 8px;
      border: 1px solid #dee2e6;
      box-shadow: 0 2px 5px rgba(0,0,0,0.05);
    }
    
    .entry-info h5 {
      color: #495057;
      margin-bottom: 15px;
      display: flex;
      align-items: center;
      gap: 8px;
    }
    
    .info-item {
      margin-bottom: 10px;
    }
    
    .info-label {
      font-weight: bold;
      color: #6c757d;
    }
    
    .text-content {
      background: #f8f9fa;
      padding: 15px;
      border-radius: 4px;
      border: 1px solid #e9ecef;
      max-height: 300px;
      overflow-y: auto;
      font-family: 'Consolas', 'Monaco', monospace;
      font-size: 0.95em;
      line-height: 1.5;
      white-space: pre-wrap;
      word-break: break-word;
    }
    
    .text-content-preview {
      max-height: 120px;
      overflow: hidden;
      position: relative;
    }
    
    .text-content-full {
      max-height: none;
    }
    
    .text-expand-btn {
      display: block;
      width: 100%;
      text-align: center;
      margin-top: 5px;
      padding: 4px;
      background: #f8f9fa;
      border: 1px solid #dee2e6;
      border-radius: 0 0 4px 4px;
      cursor: pointer;
      color: #007bff;
      font-size: 0.9em;
    }
    
    .text-content-fade {
      position: absolute;
      bottom: 0;
      left: 0;
      width: 100%;
      height: 40px;
      background: linear-gradient(to bottom, rgba(248,249,250,0), rgba(248,249,250,1));
      pointer-events: none;
    }
    
    .text-content-wrapper {
      position: relative;
    }
    
    .copy-btn {
      position: absolute;
      top: 10px;
      right: 10px;
      background: #fff;
      border: 1px solid #dee2e6;
      border-radius: 4px;
      padding: 3px 8px;
      font-size: 0.8em;
      cursor: pointer;
      z-index: 10;
    }
    
    .copy-btn:hover {
      background: #f8f9fa;
    }
    
    .loading-spinner {
      display: none;
      position: absolute;
      top: 50%;
      left: 50%;
      transform: translate(-50%, -50%);
      z-index: 100;
    }
    
    .current-time {
      font-size: 1.1em;
      font-weight: 500;
      color: #495057;
    }
    
    .timeline-stats {
      font-size: 0.9em;
      color: #6c757d;
    }
    
    .search-card-text {
      max-height: 80px;
      overflow: hidden;
      font-family: 'Consolas', 'Monaco', monospace;
      font-size: 0.85em;
      white-space: pre-wrap;
      word-break: break-word;
    }
    
    .modal-text-content {
      background: white;
      padding: 15px;
      border-radius: 4px;
      border: 1px solid #dee2e6;
      max-height: 400px;
      overflow-y: auto;
      font-family: 'Consolas', 'Monaco', monospace;
      font-size: 0.95em;
      line-height: 1.5;
      white-space: pre-wrap;
      word-break: break-word;
    }
    
    @media (max-width: 768px) {
      .timeline-info {
        flex-direction: column;
        gap: 10px;
        align-items: stretch;
      }
      
      .timeline-controls {
        justify-content: center;
      }
      
      .app-legend {
        justify-content: center;
      }
      
      .entry-info {
        margin-top: 15px;
      }
    }
    .navbar-content {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 100%;
}

.app-btn {
  width: 38px;
  height: 38px;
  border: 1px solid #ced4da;
  border-radius: 6px;
  background: #fff;
  color: #6c757d;
  cursor: pointer;
  transition: all 0.2s ease;
  display: flex;
  align-items: center;
  justify-content: center;
  margin-right: 8px;
  flex-shrink: 0;
}

.app-btn:hover {
  background: #f8f9fa;
  border-color: #adb5bd;
  color: #495057;
}

.app-btn:disabled {
    color: light-dark(rgba(16, 16, 16, 0.3), rgba(255, 255, 255, 0.3));
}

.search-form {
  display: flex;
  align-items: center;
  max-width: 500px;
  width: 100%;
}

.search-input-group {
  display: flex;
  width: 100%;
  border-radius: 6px;
  overflow: hidden;
  border: 1px solid #ced4da;
}

.search-input {
  flex: 1;
  border: none;
  outline: none;
  padding: 9px 16px;
  font-size: 14px;
}

.search-btn {
  width: 38px;
  height: 38px;
  border: none;
  background: #fff;
  color: #6c757d;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  border-left: 1px solid #ced4da;
}

.search-btn:hover {
  background: #f8f9fa;
  color: #495057;
}

.navbar-spacer {
  width: 46px; /* Home button width + margin for perfect symmetry */
  flex-shrink: 0;
}
  </style>
</head>
<body>
<nav class="navbar navbar-light bg-light">
  <div class="container">
    <div class="navbar-content">
      <!-- Home Button -->
      <button class="app-btn" onclick="window.location.href='/'" title="Home">
        <i class="bi bi-house-fill"></i>
      </button>
      
      <!-- Search Form -->
      <form class="search-form" action="/search" method="get">
        <div class="search-input-group">
          <input class="search-input" type="search" name="q" placeholder="Search" 
                 aria-label="Search" value="{{ request.args.get('q', '') }}">
          <button class="search-btn" type="submit" title="Search">
            <i class="bi bi-search"></i>
          </button>
        </div>
      </form>
      
      <!-- Spacer for symmetry -->
      <div class="navbar-spacer"></div>
    </div>
  </div>
</nav>
{% block content %}

{% endblock %}

  <!-- Bootstrap and jQuery JS -->
  <script src="https://code.jquery.com/jquery-3.5.1.slim.min.js"></script>
  <script src="https://cdn.jsdelivr.net/npm/@popperjs/core@2.5.3/dist/umd/popper.min.js"></script>
  <script src="https://stackpath.bootstrapcdn.com/bootstrap/4.5.2/js/bootstrap.min.js"></script>
  
  <script>
    // Function to toggle text content expansion
    function toggleTextExpand(btnElement) {
      const textContainer = btnElement.previousElementSibling;
      const fadeElement = textContainer.querySelector('.text-content-fade');
      
      if (textContainer.classList.contains('text-content-preview')) {
        // Expand
        textContainer.classList.remove('text-content-preview');
        textContainer.classList.add('text-content-full');
        btnElement.textContent = 'Show Less';
        if (fadeElement) fadeElement.style.display = 'none';
      } else {
        // Collapse
        textContainer.classList.remove('text-content-full');
        textContainer.classList.add('text-content-preview');
        btnElement.textContent = 'Show More';
        if (fadeElement) fadeElement.style.display = 'block';
      }
    }
    
    // Function to copy text to clipboard
    function copyTextToClipboard(textContent) {
      navigator.clipboard.writeText(textContent).then(function() {
        alert('Text copied to clipboard!');
      }, function(err) {
        console.error('Could not copy text: ', err);
      });
    }

    // Add this new function after the existing copyTextToClipboard function
    function toggleMarkdownView(btnElement, text) {
      const textWrapper = btnElement.closest('.text-content-wrapper');
      const textContent = textWrapper.querySelector('.text-content');
      
      // Check if markdown view already exists
      let markdownContainer = textWrapper.querySelector('.markdown-container');
      
      if (!markdownContainer) {
        // Create markdown container
        markdownContainer = document.createElement('div');
        markdownContainer.className = 'markdown-container';
        markdownContainer.style.display = 'none';
        
        // Add view toggle buttons
        markdownContainer.innerHTML = `
          <div class="text-view-toggle">
            <button class="view-mode-btn" onclick="showRawText(this)">Raw Text</button>
            <button class="view-mode-btn active" onclick="showMarkdownView(this)">Markdown View</button>
          </div>
          <div class="markdown-view">
            <div class="text-center">
              <div class="spinner-border spinner-border-sm" role="status">
                <span class="sr-only">Converting...</span>
              </div>
              <div class="ml-2">Converting to markdown...</div>
            </div>
          </div>
        `;
        
        textWrapper.appendChild(markdownContainer);
        
        // Convert text to markdown
        convertToMarkdown(text, markdownContainer.querySelector('.markdown-view'));
      }
      
      // Toggle visibility
      if (markdownContainer.style.display === 'none') {
        textContent.style.display = 'none';
        markdownContainer.style.display = 'block';
        btnElement.innerHTML = '<i class="bi bi-file-text"></i> Raw';
      } else {
        textContent.style.display = 'block';
        markdownContainer.style.display = 'none';
        btnElement.innerHTML = '<i class="bi bi-markdown"></i> Markdown';
      }
    }

    async function convertToMarkdown(text, targetElement) {
      try {
        const response = await fetch('/api/markdown-convert', {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
          },
          body: JSON.stringify({ text: text })
        });
        
        if (!response.ok) {
          throw new Error(`HTTP ${response.status}: ${response.statusText}`);
        }
        
        const data = await response.json();
        
        if (data.error) {
          throw new Error(data.error);
        }
        
        targetElement.innerHTML = data.html;
        
      } catch (error) {
        console.error('Error converting markdown:', error);
        targetElement.innerHTML = `
          <div class="alert alert-warning">
            <strong>Markdown conversion failed:</strong> ${error.message}
            <hr>
            <pre style="white-space: pre-wrap; font-size: 0.9em;">${text}</pre>
          </div>
        `;
      }
    }

    function showRawText(btn) {
      const container = btn.closest('.markdown-container');
      const textWrapper = container.closest('.text-content-wrapper');
      const textContent = textWrapper.querySelector('.text-content');
      
      // Update button states
      container.querySelector('.view-mode-btn.active').classList.remove('active');
      btn.classList.add('active');
      
      // Show raw text
      textContent.style.display = 'block';
      container.style.display = 'none';
      
      // Update main button
      const markdownBtn = textWrapper.querySelector('.markdown-btn');
      markdownBtn.innerHTML = '<i class="bi bi-markdown"></i> Markdown';
    }

    function showMarkdownView(btn) {
      const container = btn.closest('.markdown-container');
      
      // Update button states
      container.querySelector('.view-mode-btn.active').classList.remove('active');
      btn.classList.add('active');
      
      // This function is called when already in markdown view, so no action needed
    }
  </script>
  <style>
  /* Fixed zoom modal CSS - replace the existing zoom modal styles */

#zoomModal {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.9);
  display: flex;
  justify-content: center;
  align-items: center;
  z-index: 2000;
  opacity: 0;
  visibility: hidden;
  transition: opacity 0.3s ease, visibility 0.3s ease;
}

#zoomModal.show {
  opacity: 1;
  visibility: visible;
}

#zoomModal.init-hidden {
  display: none !important;
}

#zoomOverlay {
  position: absolute;
  inset: 0;
  cursor: pointer;
}

#zoomContent {
  position: relative;
  max-width: 95vw;
  max-height: 95vh;
  overflow: hidden;
  box-shadow: 0 0 20px rgba(0, 0, 0, 0.7);
  border-radius: 10px;
  background: #000;
  display: flex;
  justify-content: center;
  align-items: center;
}

#zoomImg {
  display: block;
  max-width: 95vw;
  max-height: 95vh;
  cursor: grab;
  transition: transform 0.1s ease-out;
  transform-origin: center center;
  user-select: none;
  -webkit-user-select: none;
  -moz-user-select: none;
  -ms-user-select: none;
}

#zoomImg:active {
  cursor: grabbing;
}

.zoom-controls {
  position: absolute;
  top: 10px;
  left: 10px;
  z-index: 10;
  display: flex;
  gap: 6px;
}

.zoom-controls button,
#zoomClose {
  font-size: 1.25rem;
  padding: 6px 10px;
  background: rgba(0, 0, 0, 0.6);
  color: #fff;
  border: none;
  border-radius: 6px;
  cursor: pointer;
  backdrop-filter: blur(4px);
  transition: background 0.2s ease;
  user-select: none;
  -webkit-user-select: none;
}

.zoom-controls button:hover,
#zoomClose:hover {
  background: rgba(255, 255, 255, 0.15);
}

.zoom-controls button:active,
#zoomClose:active {
  background: rgba(255, 255, 255, 0.25);
}

#zoomClose {
  position: absolute;
  top: 10px;
  right: 10px;
  width: 36px;
  height: 36px;
  font-size: 1.5rem;
  line-height: 1;
  text-align: center;
  padding: 0;
  display: flex;
  align-items: center;
  justify-content: center;
}

/* Prevent text selection during drag */
#zoomModal.dragging {
  user-select: none;
  -webkit-user-select: none;
  -moz-user-select: none;
  -ms-user-select: none;
}

/* Ensure modal appears above Bootstrap modals */
#zoomModal {
  z-index: 2000;
}
</style>

<script>
  let zoomModal = null;
  let zoomImage = null;
  let zoomLevel = 1;
  let isDragging = false;
  let dragStart = { x: 0, y: 0 };
  let imageOffset = { x: 0, y: 0 };

  // Modal init on page load
  window.addEventListener('DOMContentLoaded', () => {
    // Create modal structure
    zoomModal = document.createElement('div');
    zoomModal.id = 'zoomModal';
    zoomModal.className = 'init-hidden'; // Start hidden
    zoomModal.innerHTML = `
      <div id="zoomOverlay"></div>
      <div id="zoomContent">
        <img id="zoomImg" draggable="false" />
        <div class="zoom-controls">
          <button id="zoomInBtn">+</button>
          <button id="zoomOutBtn">-</button>
        </div>
        <button id="zoomClose">&times;</button>
      </div>
    `;
    document.body.appendChild(zoomModal);

    // Get references after adding to DOM
    zoomImage = document.getElementById('zoomImg');
    
    // Bind events
    document.getElementById('zoomOverlay').onclick = closeZoomModal;
    document.getElementById('zoomClose').onclick = closeZoomModal;
    document.getElementById('zoomInBtn').onclick = zoomIn;
    document.getElementById('zoomOutBtn').onclick = zoomOut;
    
    // Keyboard events
    document.addEventListener('keydown', (e) => {
      if (zoomModal && zoomModal.classList.contains('show')) {
        if (e.key === 'Escape') {
          closeZoomModal();
        }
      }
    });

    // Mouse wheel zoom
    zoomModal.addEventListener('wheel', (e) => {
      if (zoomModal.classList.contains('show')) {
        e.preventDefault();
        if (e.deltaY < 0) {
          zoomIn();
        } else {
          zoomOut();
        }
      }
    }, { passive: false });

    // Drag functionality
    const zoomContent = document.getElementById('zoomContent');

    zoomContent.addEventListener('mousedown', (e) => {
      // Don't start dragging if clicking on buttons
      if (e.target.closest('button')) return;

      isDragging = true;
      dragStart = { x: e.clientX, y: e.clientY };
      zoomImage.style.cursor = 'grabbing';
      e.preventDefault();
    });

    document.addEventListener('mousemove', (e) => {
      if (!isDragging || !zoomModal.classList.contains('show')) return;
      
      const deltaX = e.clientX - dragStart.x;
      const deltaY = e.clientY - dragStart.y;
      
      imageOffset.x += deltaX;
      imageOffset.y += deltaY;
      
      dragStart = { x: e.clientX, y: e.clientY };
      applyZoom();
    });

    document.addEventListener('mouseup', () => {
      if (isDragging) {
        isDragging = false;
        if (zoomImage) {
          zoomImage.style.cursor = 'grab';
        }
      }
    });

    // Touch events for mobile
    zoomContent.addEventListener('touchstart', (e) => {
      if (e.target.closest('button')) return;
      
      e.preventDefault();
      const touch = e.touches[0];
      isDragging = true;
      dragStart = { x: touch.clientX, y: touch.clientY };
    });

    document.addEventListener('touchmove', (e) => {
      if (!isDragging || !zoomModal.classList.contains('show')) return;
      
      e.preventDefault();
      const touch = e.touches[0];
      const deltaX = touch.clientX - dragStart.x;
      const deltaY = touch.clientY - dragStart.y;
      
      imageOffset.x += deltaX;
      imageOffset.y += deltaY;
      
      dragStart = { x: touch.clientX, y: touch.clientY };
      applyZoom();
    });

    document.addEventListener('touchend', () => {
      isDragging = false;
    });
  });

  function openZoomModal(src) {
    if (!zoomModal || !zoomImage) {
      console.error('Zoom modal not initialized');
      return;
    }
    
    // Reset zoom and position
    zoomLevel = 1;
    imageOffset = { x: 0, y: 0 };

    // Set up image load handler
    zoomImage.onload = () => {
      applyZoom();
      zoomImage.style.cursor = 'grab';
    };

    zoomImage.onerror = () => {
      console.error('Failed to load image:', src);
    };

    // Load the image
    zoomImage.src = src;
    
    // Show modal
    zoomModal.classList.remove('init-hidden');
    zoomModal.style.display = 'flex';
    
    // Trigger show animation
    requestAnimationFrame(() => {
      zoomModal.classList.add('show');
    });
  }

  function closeZoomModal() {
    if (!zoomModal) return;
    
    zoomModal.classList.remove('show');
    
    setTimeout(() => {
      zoomModal.style.display = 'none';
      // Reset image
      if (zoomImage) {
        zoomImage.src = '';
        zoomLevel = 1;
        imageOffset = { x: 0, y: 0 };
      }
    }, 300);
  }

  function zoomIn() {
    zoomLevel = Math.min(zoomLevel + 0.2, 5); // Max 5x zoom
    applyZoom();
  }

  function zoomOut() {
    zoomLevel = Math.max(zoomLevel - 0.2, 0.2); // Min 0.2x zoom
    applyZoom();
  }

  function applyZoom() {
    if (zoomImage) {
      const transform = `translate(${imageOffset.x}px, ${imageOffset.y}px) scale(${zoomLevel})`;
      zoomImage.style.transform = transform;
    }
  }

  // Make openZoomModal globally available
  window.openZoomModal = openZoomModal;
</script>

</body>
</html>
"""


class StringLoader(BaseLoader):
    def get_source(self, environment, template):
        if template == "base_template":
            return base_template, None, lambda: True
        return None, None, None


app.jinja_env.loader = StringLoader()


def get_entry_by_timestamp(timestamp):
    """Get database entry by timestamp"""
    entries = get_all_entries()
    for entry in entries:
        if entry.timestamp == timestamp:
            return entry
    return None

def generate_app_colors():
    """Generate consistent colors for apps"""
    colors = [
        '#FF6B6B', '#4ECDC4', '#45B7D1', '#96CEB4', '#FFEAA7',
        '#DDA0DD', '#98D8C8', '#F7DC6F', '#BB8FCE', '#85C1E9',
        '#F8C471', '#82E0AA', '#F1948A', '#85C1E9', '#D7BDE2',
        '#A3E4D7', '#FAD7A0', '#D5A6BD', '#AED6F1', '#A9DFBF'
    ]
    return colors

def get_app_color_mapping(entries):
    """Create a consistent color mapping for apps"""
    apps = list(set(entry.app for entry in entries if entry.app))
    colors = generate_app_colors()
    
    app_colors = {}
    for i, app in enumerate(sorted(apps)):
        app_colors[app] = colors[i % len(colors)]
    
    # Default color for unknown apps - use string instead of None
    app_colors['Unknown'] = '#9E9E9E'
    
    return app_colors

# JavaScript template for timeline functionality
timeline_js_template = '''
class EnhancedTimeline {
  constructor() {
    this.currentIndex = 0;
    this.entries = TEMPLATE_DATA_entries || {};
    this.timestamps = TEMPLATE_DATA_timestamps || [];
    this.appColors = TEMPLATE_DATA_app_colors || {};
    this.totalCount = TEMPLATE_DATA_total_count || 0;
    this.isLoading = false;
    this.isDragging = false;
    this.dragStartX = 0;
    this.trackOffset = 0;
    this.segmentWidth = 12;
    this.visibleSegments = 0;
    
    this.initializeElements();
    this.bindEvents();
    
    if (this.timestamps.length > 0) {
      this.updateVisibleSegments();
      this.navigateToIndex(0); // Start with latest entry (index 0)
      this.updateStats();
      // Center the timeline on the current segment
      setTimeout(() => this.centerCurrentSegment(), 100);
    }
    
    this.loadTimelineData();
  }
  
  initializeElements() {
    this.timelineTrack = document.getElementById('timelineTrack');
    this.timelineWrapper = document.getElementById('timelineWrapper');
    this.positionIndicator = document.getElementById('positionIndicator');
    this.currentTimeEl = document.getElementById('currentTime');
    this.timelineStatsEl = document.getElementById('timelineStats');
    this.appLegendEl = document.getElementById('appLegend');
    this.timestampImage = document.getElementById('timestampImage');
    this.imageSpinner = document.getElementById('imageSpinner');
    this.entryDetails = document.getElementById('entryDetails');
    this.prevBtn = document.getElementById('prevBtn');
    this.nextBtn = document.getElementById('nextBtn');
    this.refreshBtn = document.getElementById('refreshBtn');
  }
  
  bindEvents() {
    this.prevBtn.addEventListener('click', () => this.navigateToIndex(this.currentIndex - 1));
    this.nextBtn.addEventListener('click', () => this.navigateToIndex(this.currentIndex + 1));
    this.refreshBtn.addEventListener('click', () => this.loadTimelineData(true));
    
    document.addEventListener('keydown', (e) => {
      if (e.target.tagName === 'INPUT') return;
      
      switch(e.key) {
        case 'ArrowLeft':
          e.preventDefault();
          this.navigateToIndex(this.currentIndex - 1);
          break;
        case 'ArrowRight':
          e.preventDefault();
          this.navigateToIndex(this.currentIndex + 1);
          break;
        case 'Home':
          e.preventDefault();
          this.navigateToIndex(0);
          break;
        case 'End':
          e.preventDefault();
          this.navigateToIndex(this.timestamps.length - 1);
          break;
      }
    });
    
    // Timeline segment click events
    this.timelineTrack.addEventListener('click', (e) => {
      if (e.target.classList.contains('timeline-segment')) {
        const index = parseInt(e.target.dataset.index);
        if (!isNaN(index)) {
          this.navigateToIndex(index);
        }
      }
    });
    
    // Timeline dragging events
    this.timelineWrapper.addEventListener('mousedown', (e) => this.handleDragStart(e));
    document.addEventListener('mousemove', (e) => this.handleDragMove(e));
    document.addEventListener('mouseup', () => this.handleDragEnd());
    
    // Touch events for mobile
    this.timelineWrapper.addEventListener('touchstart', (e) => {
      e.preventDefault();
      this.handleDragStart(e.touches[0]);
    });
    document.addEventListener('touchmove', (e) => {
      if (this.isDragging) {
        e.preventDefault();
        this.handleDragMove(e.touches[0]);
      }
    });
    document.addEventListener('touchend', () => this.handleDragEnd());
    
    // Prevent context menu on timeline
    this.timelineWrapper.addEventListener('contextmenu', (e) => e.preventDefault());
    
    // Window resize
    window.addEventListener('resize', () => {
      this.updateVisibleSegments();
      this.centerCurrentSegment();
    });
  }
  
  async loadTimelineData(forceRefresh = false) {
    if (this.isLoading && !forceRefresh) return;
    
    this.isLoading = true;
    this.showLoading();
    
    try {
      const response = await fetch('/api/timeline-data?page=0&page_size=100');
      
      if (!response.ok) {
        throw new Error('HTTP ' + response.status + ': ' + response.statusText);
      }
      
      const data = await response.json();
      
      if (data.error) {
        throw new Error(data.error);
      }
      
      if (data.entries && Object.keys(data.entries).length > 0) {
        this.entries = data.entries;
        this.timestamps = data.timestamps || [];
        this.appColors = data.app_colors || {};
        this.totalCount = data.total_count || 0;
        
        this.renderTimeline();
        this.updateVisibleSegments();
        this.navigateToIndex(0);
        this.updateStats();
        // Center the timeline after loading new data
        setTimeout(() => this.centerCurrentSegment(), 100);
      }
      
    } catch (error) {
      console.error('Error loading timeline data:', error);
      if (this.timestamps.length === 0) {
        this.showError(error.message);
      }
    } finally {
      this.isLoading = false;
      this.hideLoading();
    }
  }
  
  renderTimeline() {
    this.timelineTrack.innerHTML = '';
    
    if (this.timestamps.length === 0) return;
    
    this.timestamps.forEach((timestamp, index) => {
      const entry = this.entries[timestamp.toString()];
      if (!entry) return;
      
      const segment = document.createElement('div');
      segment.className = 'timeline-segment';
      segment.style.backgroundColor = this.appColors[entry.app] || this.appColors['Unknown'] || '#9E9E9E';
      segment.style.width = this.segmentWidth + 'px';
      segment.title = entry.app + ' - ' + new Date(timestamp * 1000).toLocaleString();
      segment.dataset.index = index;
      segment.dataset.timestamp = timestamp;
      
      segment.addEventListener('click', (e) => {
        e.preventDefault();
        this.navigateToIndex(index);
      });
      
      this.timelineTrack.appendChild(segment);
    });
    
    this.renderAppLegend();
  }
  
  renderAppLegend() {
    if (!this.appColors || Object.keys(this.appColors).length === 0) {
      this.appLegendEl.innerHTML = apps.map(app => 
      '<div class="app-legend-item">' +
        '<div class="app-color-dot" style="background-color: ' + this.appColors[app] + '"></div>' +
        '<span>' + app + '</span>' +
      '</div>'
    ).join('');
  }
  
  updateVisibleSegments() {
    const wrapperWidth = this.timelineWrapper.offsetWidth;
    this.visibleSegments = Math.floor(wrapperWidth / (this.segmentWidth + 2));
  }
  
  navigateToIndex(index) {
    if (index < 0 || index >= this.timestamps.length) return;
    
    const previousActive = this.timelineTrack.querySelector('.timeline-segment.active');
    if (previousActive) {
      previousActive.classList.remove('active');
    }
    
    const newActive = this.timelineTrack.querySelector('[data-index="' + index + '"]');
    if (newActive) {
      newActive.classList.add('active');
    }
    
    this.currentIndex = index;
    this.updateContent();
    this.updatePositionIndicator();
    this.updateNavigationButtons();
    this.centerCurrentSegment();
  }
  
  centerCurrentSegment() {
    if (this.timestamps.length === 0) return;
    
    const segment = this.timelineTrack.querySelector('[data-index="' + this.currentIndex + '"]');
    if (!segment) return;
    
    const wrapperWidth = this.timelineWrapper.offsetWidth;
    const segmentRect = segment.getBoundingClientRect();
    const wrapperRect = this.timelineWrapper.getBoundingClientRect();
    
    // Calculate the offset needed to center the segment
    const segmentCenter = segmentRect.left - wrapperRect.left + (segmentRect.width / 2);
    const wrapperCenter = wrapperWidth / 2;
    const targetOffset = wrapperCenter - segmentCenter;
    
    // Constrain the offset to valid bounds
    const maxOffset = 0;
    const minOffset = Math.min(0, wrapperWidth - this.timelineTrack.offsetWidth);
    
    this.trackOffset = Math.max(minOffset, Math.min(maxOffset, this.trackOffset + targetOffset));
    this.timelineTrack.style.transform = 'translateX(' + this.trackOffset + 'px)';
  }
  
  updateContent() {
    const timestamp = this.timestamps[this.currentIndex];
    const entry = this.entries[timestamp.toString()];
    
    if (!entry) return;
    
    this.currentTimeEl.textContent = new Date(timestamp * 1000).toLocaleString();
    
    this.timestampImage.style.display = 'none';
    this.imageSpinner.style.display = 'block';
    
    const img = new Image();
    img.onload = () => {
      this.timestampImage.src = img.src;
      this.timestampImage.style.display = 'block';
      this.imageSpinner.style.display = 'none';
    };
    img.onerror = () => {
      this.timestampImage.alt = 'Image not found';
      this.timestampImage.style.display = 'block';
      this.imageSpinner.style.display = 'none';
    };
    img.src = '/static/' + timestamp + '.webp';
    
    this.updateEntryDetails(entry);
  }
  
  updateEntryDetails(entry) {
  let textContentHtml = '';
  
  if (entry.text && entry.text.trim()) {
    const needsExpand = entry.text.length > 300;
    // Properly escape text for HTML and JavaScript
    const escapedText = entry.text
      .replace(/\\/g, '\\\\')
      .replace(/'/g, "\\'")
      .replace(/"/g, '\\"')
      .replace(/`/g, '\\`')
      .replace(/\n/g, '\\n')
      .replace(/\r/g, '\\r');
    
    textContentHtml = 
      '<div class="text-content-wrapper">' +
        '<div class="text-content ' + (needsExpand ? 'text-content-preview' : '') + '">' +
          entry.text +
          (needsExpand ? '<div class="text-content-fade"></div>' : '') +
        '</div>' +
        (needsExpand ? '<button class="text-expand-btn" onclick="toggleTextExpand(this)">Show More</button>' : '') +
        '<button class="markdown-btn" onclick="toggleMarkdownView(this, \'' + escapedText + '\')">' +
          '<i class="bi bi-markdown"></i> Markdown' +
        '</button>' +
        '<button class="copy-btn" onclick="copyTextToClipboard(\'' + escapedText + '\')">' +
          '<i class="bi bi-clipboard"></i> Copy' +
        '</button>' +
      '</div>';
  } else {
    textContentHtml = '<div class="text-muted">No text extracted</div>';
  }
  
  const color = this.appColors[entry.app] || this.appColors['Unknown'] || '#9E9E9E';
  
  this.entryDetails.innerHTML = 
    '<div class="info-item">' +
      '<span class="info-label">App:</span> ' +
      '<span style="color: ' + color + '">● ' + (entry.app || 'Unknown') + '</span>' +
    '</div>' +
    '<div class="info-item">' +
      '<span class="info-label">Title:</span> ' + (entry.title || 'No title') +
    '</div>' +
    '<div class="info-item">' +
      '<span class="info-label">Time:</span> ' + new Date(entry.timestamp * 1000).toLocaleString() +
    '</div>' +
    '<div class="info-item">' +
      '<span class="info-label">Position:</span> ' + (this.currentIndex + 1) + ' of ' + this.dayEntries.length +
      ' <small class="text-muted">(' + (this.currentIndex === 0 ? 'Latest' : this.currentIndex === this.dayEntries.length - 1 ? 'Oldest' : 'Middle') + ')</small>' +
    '</div>' +
    '<div class="info-item">' +
      '<span class="info-label">Extracted Text:</span>' + textContentHtml +
    '</div>';
}
  
  updatePositionIndicator() {
    if (this.timestamps.length === 0) return;
    
    // Always position the indicator at the center of the wrapper
    const wrapperCenter = this.timelineWrapper.offsetWidth / 2;
    this.positionIndicator.style.left = wrapperCenter + 'px';
  }
  
  updateNavigationButtons() {
    this.prevBtn.disabled = this.currentIndex <= 0;
    this.nextBtn.disabled = this.currentIndex >= this.timestamps.length - 1;
  }
  
  updateStats() {
    const uniqueApps = new Set(Object.values(this.entries).map(e => e.app)).size;
    this.timelineStatsEl.textContent = this.timestamps.length + ' snapshots • ' + uniqueApps + ' apps';
  }
  
  ensureSegmentVisible(index) {
    const segment = this.timelineTrack.querySelector('[data-index="' + index + '"]');
    if (!segment) return;
    
    const segmentRect = segment.getBoundingClientRect();
    const wrapperRect = this.timelineWrapper.getBoundingClientRect();
    
    if (segmentRect.left < wrapperRect.left || segmentRect.right > wrapperRect.right) {
      const segmentCenter = segmentRect.left + segmentRect.width / 2;
      const wrapperCenter = wrapperRect.left + wrapperRect.width / 2;
      const offset = segmentCenter - wrapperCenter;
      
      this.trackOffset -= offset;
      this.trackOffset = Math.max(
        -(this.timelineTrack.offsetWidth - this.timelineWrapper.offsetWidth),
        Math.min(0, this.trackOffset)
      );
      
      this.timelineTrack.style.transform = 'translateX(' + this.trackOffset + 'px)';
    }
  }
  
  handleDragStart(e) {
    this.isDragging = true;
    this.dragStartX = e.clientX;
    this.initialTrackOffset = this.trackOffset;
    this.timelineWrapper.style.cursor = 'grabbing';
    this.timelineTrack.style.transition = 'none';
    
    // Prevent text selection during drag
    document.body.style.userSelect = 'none';
  }
  
  handleDragMove(e) {
    if (!this.isDragging) return;
    
    const deltaX = e.clientX - this.dragStartX;
    const newOffset = this.initialTrackOffset + deltaX;
    
    // Constrain the offset
    const maxOffset = 0;
    const minOffset = Math.min(0, this.timelineWrapper.offsetWidth - this.timelineTrack.offsetWidth);
    this.trackOffset = Math.max(minOffset, Math.min(maxOffset, newOffset));
    
    this.timelineTrack.style.transform = 'translateX(' + this.trackOffset + 'px)';
    
    // Update position indicator during drag
    this.updatePositionIndicator();
  }
  
  handleDragEnd() {
    if (!this.isDragging) return;
    
    this.isDragging = false;
    this.timelineWrapper.style.cursor = 'grab';
    this.timelineTrack.style.transition = 'transform 0.3s cubic-bezier(0.25, 0.46, 0.45, 0.94)';
    document.body.style.userSelect = '';
    
    // Snap to nearest segment after drag
    this.snapToNearestSegment();
  }
  
  snapToNearestSegment() {
    if (this.timestamps.length === 0) return;
    
    const wrapperCenter = this.timelineWrapper.offsetWidth / 2;
    let closestIndex = 0;
    let minDistance = Infinity;
    
    // Find the segment closest to the center
    for (let i = 0; i < this.timestamps.length; i++) {
      const segment = this.timelineTrack.querySelector('[data-index="' + i + '"]');
      if (!segment) continue;
      
      const segmentRect = segment.getBoundingClientRect();
      const wrapperRect = this.timelineWrapper.getBoundingClientRect();
      const segmentCenter = segmentRect.left - wrapperRect.left + (segmentRect.width / 2);
      const distance = Math.abs(segmentCenter - wrapperCenter);
      
      if (distance < minDistance) {
        minDistance = distance;
        closestIndex = i;
      }
    }
    
    // Navigate to the closest segment
    if (closestIndex !== this.currentIndex) {
      this.navigateToIndex(closestIndex);
    } else {
      // Just center the current segment if it's already the closest
      this.centerCurrentSegment();
    }
  }
  
  showLoading() {
    const spinner = document.querySelector('.timeline-container .loading-spinner');
    if (spinner) {
      spinner.style.display = 'block';
    }
  }
  
  hideLoading() {
    const spinner = document.querySelector('.timeline-container .loading-spinner');
    if (spinner) {
      spinner.style.display = 'none';
    }
  }
  
  showEmptyState() {
    this.timelineStatsEl.textContent = 'No snapshots found. Wait a few seconds for recording to start.';
    this.currentTimeEl.textContent = 'No data available';
    this.entryDetails.innerHTML = '<div class="alert alert-info">Nothing recorded yet, wait a few seconds.</div>';
    this.timelineTrack.innerHTML = '';
    this.appLegendEl.innerHTML = '<div class="text-muted">No data available</div>';
  }
  
  showError(message) {
    this.timelineStatsEl.textContent = 'Error loading timeline data';
    this.currentTimeEl.textContent = 'Error';
    this.entryDetails.innerHTML = '<div class="alert alert-danger">Error loading timeline: ' + message + '</div>';
    this.timelineTrack.innerHTML = '';
    this.appLegendEl.innerHTML = '<div class="text-danger">Error loading apps</div>';
  }
}

document.addEventListener('DOMContentLoaded', () => {
  window.timeline = new EnhancedTimeline();
  
  setInterval(() => {
    if (!window.timeline.isLoading) {
      window.timeline.loadTimelineData();
    }
  }, 30000);
});
'''


@app.route("/api/available-dates")
def available_dates():
    """Get all available dates that have entries"""
    try:
        entries = get_all_entries()
        if not entries:
            return jsonify({'dates': []})
        
        # Group entries by date
        dates = set()
        for entry in entries:
            # Convert timestamp to date string (YYYY-MM-DD)
            date = datetime.fromtimestamp(entry.timestamp).date()
            dates.add(date.isoformat())
        
        # Sort dates in descending order (newest first)
        sorted_dates = sorted(list(dates), reverse=True)
        
        return jsonify({'dates': sorted_dates})
        
    except Exception as e:
        print(f"API Error: {e}")
        return jsonify({'error': str(e)}), 500


@app.route("/api/day-entries")
def day_entries():
    """Get all entries for a specific date"""
    try:
        date_str = request.args.get('date')
        if not date_str:
            return jsonify({'error': 'Date parameter required'}), 400
        
        # Parse the date
        try:
            target_date = datetime.strptime(date_str, '%Y-%m-%d').date()
        except ValueError:
            return jsonify({'error': 'Invalid date format. Use YYYY-MM-DD'}), 400
        
        entries = get_all_entries()
        
        # Filter entries for the specific date
        day_entries = []
        for entry in entries:
            entry_date = datetime.fromtimestamp(entry.timestamp).date()
            if entry_date == target_date:
                day_entries.append({
                    'app': entry.app or 'Unknown',
                    'title': entry.title or 'No title',
                    'text': entry.text or '',
                    'timestamp': entry.timestamp
                })
        
        # Sort by timestamp (newest first)
        day_entries.sort(key=lambda x: x['timestamp'], reverse=True)
        
        # Get app color mapping for this day's entries
        if day_entries:
            # Create mock entry objects for the color mapping function
            mock_entries = []
            for entry_data in day_entries:
                mock_entry = type('Entry', (), entry_data)()
                mock_entries.append(mock_entry)
            app_colors = get_app_color_mapping(mock_entries)
        else:
            app_colors = {}
        
        return jsonify({
            'entries': day_entries,
            'app_colors': app_colors,
            'date': date_str,
            'count': len(day_entries)
        })
        
    except Exception as e:
        print(f"API Error: {e}")
        return jsonify({'error': str(e)}), 500


# Update your main timeline route to use the new template
@app.route("/")
def timeline():
    return render_template_string(
        """
{% extends "base_template" %}
{% block content %}
<div class="container">
  <!-- Date Selection Controls -->
  <div class="date-selector-container">
    <div class="date-controls">
      <button class="btn btn-outline-secondary" id="nextDayBtn" title="Previous Day (Page Down)">
        <i class="bi bi-arrow-left"></i>
      </button>
      <select class="form-control date-selector" id="dateSelector">
        <option value="">Loading dates...</option>
      </select>
      <button class="btn btn-outline-secondary" id="prevDayBtn" title="Next Day (Page Up)">
        <i class="bi bi-arrow-right"></i>
      </button>
    </div>
    <button class="app-btn"  id="refreshBtn" title="Refresh Current Day">
      <i class="bi bi-arrow-repeat"></i>
    </button>
  </div>

<!-- Recording Control Bar -->
  <div class="recording-control-container">
    <div class="recording-status">
      <div class="recording-indicator" id="recordingIndicator">
        <div class="recording-dot" id="recordingDot"></div>
        <span class="recording-text" id="recordingText">Recording</span>
      </div>
      <div class="recording-stats" id="recordingStats">
        <span class="stat-item">
          <span id="screenshotCount">0</span> snapshots
        </span>
        <span class="stat-separator">•</span>
        <span class="stat-item">
          <span id="sessionDuration">00:00</span> session
        </span>
      </div>
    </div>
    
    <div class="recording-controls">
      <button class="app-btn" id="pauseBtn" title="Pause Recording (Ctrl+Space)">
        <i class="bi bi-pause-fill"></i>
      </button>
      <button class="app-btn" id="resumeBtn" title="Resume Recording (Ctrl+Space)" style="display: none;">
        <i class="bi bi-play-fill"></i>
      </button>
      <button style="display:none;" class="app-btn" id="settingsBtn" title="Recording Settings">
        <i class="bi bi-gear"></i>
      </button>
    </div>
  </div>

  <!-- Timeline Container -->
  <div class="timeline-container">
    <div class="timeline-info">
      <div>
        <div class="current-time" id="currentTime">Loading...</div>
        <div class="timeline-stats" id="timelineStats">Loading timeline data...</div>
      </div>
      <div class="timeline-controls">
        <button class="app-btn" id="refreshBtn" title="Refresh">
          <i class="bi bi-arrow-repeat"></i>
        </button>
      </div>
    </div>
    
    <div class="timeline-wrapper-container">
      <!-- Newer button (left arrow) on left side -->
      <button class="timeline-side-btn timeline-left-btn" id="nextBtn" title="Newer (←)">
        <i class="bi bi-arrow-left"></i>
      </button>
      
      <div class="timeline-wrapper" id="timelineWrapper">
        <div class="timeline-track" id="timelineTrack">
          <!-- Segments will be dynamically loaded -->
        </div>
        <div class="timeline-position-indicator" id="positionIndicator"></div>
        <div class="loading-spinner" style="display: none;">
          <div class="spinner-border" role="status">
            <span class="sr-only">Loading...</span>
          </div>
        </div>
      </div>
      
      <!-- Older button (right arrow) on right side -->
      <button class="timeline-side-btn timeline-right-btn" id="prevBtn" title="Older (→)">
        <i class="bi bi-arrow-right"></i>
      </button>
    </div>
    
    <div class="app-legend" id="appLegend">
      <div class="text-muted">Loading apps...</div>
    </div>
  </div>
  
  <div class="content-container">
    <div class="image-container">
      <img id="timestampImage" src="" onclick="openZoomModal(this.src)" alt="Loading..." style="display: none;">
      <div class="loading-spinner" id="imageSpinner">
        <div class="spinner-border text-primary" role="status">
          <span class="sr-only">Loading...</span>
        </div>
      </div>
    </div>
    <div class="entry-info">
      <h5><i class="bi bi-database"></i> Entry Details</h5>
      <div id="entryDetails">
        <div class="text-muted">Loading entry data...</div>
      </div>
    </div>
  </div>
</div>

<style>
.date-selector-container {
  background: white;
  padding: 20px;
  border-radius: 12px;
  margin-bottom: 20px;
  box-shadow: 0 2px 10px rgba(0,0,0,0.1);
  display: flex;
  justify-content: space-between;
  align-items: center;
  flex-wrap: wrap;
  gap: 15px;
}

.date-controls {
  display: flex;
  align-items: center;
  gap: 10px;
}

.date-selector {
  min-width: 200px;
  max-width: 300px;
}

.recording-control-container {
  background: white;
  padding: 16px 20px;
  border-radius: 12px;
  margin-bottom: 20px;
  box-shadow: 0 2px 10px rgba(0,0,0,0.1);
  display: flex;
  justify-content: space-between;
  align-items: center;
  flex-wrap: wrap;
  gap: 15px;
  border: 1px solid #e9ecef;
}

.recording-status {
  display: flex;
  align-items: center;
  gap: 20px;
}

.recording-indicator {
  display: flex;
  align-items: center;
  gap: 8px;
  font-weight: 500;
  color: #495057;
}

.recording-dot {
  width: 8px;
  height: 8px;
  background: #28a745;
  border-radius: 50%;
  animation: recording-pulse 2s infinite;
}

.recording-dot.paused {
  background: #6e6e6e;
  animation: none;
}

.recording-dot.error {
  background: #dc3545;
  animation: none;
}

@keyframes recording-pulse {
  0%, 100% {
    opacity: 1;
    transform: scale(1);
  }
  50% {
    opacity: 0.6;
    transform: scale(1.1);
  }
}

.recording-stats {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 14px;
  color: #6c757d;
}

.stat-item {
  font-weight: 500;
}

.stat-separator {
  opacity: 0.5;
}

.recording-controls {
  display: flex;
  gap: 8px;
  align-items: center;
}

/* Enhance existing app-btn for recording controls */
.recording-controls .app-btn {
  transition: all 0.2s ease;
}

.recording-controls .app-btn:hover {
  transform: translateY(-1px);
  box-shadow: 0 2px 8px rgba(0,0,0,0.15);
}

.recording-controls #pauseBtn:hover {
  background: #fff5f5;
  border-color: #dc3545;
  color: #dc3545;
}

.recording-controls #resumeBtn:hover {
  background: #f0f9f0;
  border-color: #28a745;
  color: #28a745;
}

.recording-controls #settingsBtn:hover {
  background: #f8f9fa;
  border-color: #6c757d;
}

/* Paused state styling */
.recording-control-container.paused {
  border-color: #6e6e6e;
  background: linear-gradient(to right, #d6d6d6, #ffffff);
}

.recording-control-container.error {
  border-color: #dc3545;
  background: linear-gradient(to right, #fff5f5, #ffffff);
}

/* Responsive design */
@media (max-width: 768px) {
  .recording-control-container {
    flex-direction: column;
    gap: 12px;
  }
  
  .recording-status {
    flex-direction: column;
    gap: 8px;
    text-align: center;
    width: 100%;
  }
  
  .recording-controls {
    justify-content: center;
  }
}

/* Match the existing button icons */
.bi-pause-fill::before {
  font-size: 14px;
}

.bi-play-fill::before {
  font-size: 14px;
}

.bi-gear::before {
  font-size: 14px;
}

/* Date Selector Styles (keeping existing ones) */
.date-selector-container {
  background: white;
  padding: 20px;
  border-radius: 12px;
  margin-bottom: 20px;
  box-shadow: 0 2px 10px rgba(0,0,0,0.1);
  display: flex;
  justify-content: space-between;
  align-items: center;
  flex-wrap: wrap;
  gap: 15px;
}

.date-controls {
  display: flex;
  align-items: center;
  gap: 10px;
}

.date-selector {
  min-width: 200px;
  max-width: 300px;
}


.timeline-container {
    max-width: 1200px;
    margin: 20px auto;
    background: white;
    border-radius: 12px;
    padding: 20px;
    box-shadow: 0 2px 20px rgba(0,0,0,0.08);
}

.timeline-info {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 20px;
    padding-bottom: 15px;
    border-bottom: 1px solid #e5e5e5;
}

.current-time {
    font-size: 18px;
    font-weight: 600;
    color: #333;
}

.timeline-stats {
    font-size: 14px;
    color: #666;
    margin-top: 4px;
}

.timeline-controls {
    display: flex;
    gap: 8px;
}

.timeline-nav-btn {
    width: 36px;
    height: 36px;
    border: none;
    border-radius: 8px;
    background: #f8f9fa;
    color: #495057;
    cursor: pointer;
    transition: all 0.2s ease;
    display: flex;
    align-items: center;
    justify-content: center;
}

.timeline-nav-btn:hover {
    background: #e9ecef;
    color: #333;
}

.timeline-wrapper-container {
    display: flex;
    align-items: center;
    gap: 0;
    margin: 20px 0;
}

.timeline-side-btn {
    width: 40px;
    height: 60px;
    border: 1px solid #e9ecef;
    border-radius: 0;
    background: #f8f9fa;
    color: #666;
    cursor: pointer;
    transition: all 0.2s ease;
    display: flex;
    align-items: center;
    justify-content: center;
    flex-shrink: 0;
    z-index: 10;
    position: relative;
}

.timeline-side-btn.timeline-left-btn {
    border-right: 1px solid #e9ecef;
    border-radius: 8px 0 0 8px;
}

.timeline-side-btn.timeline-right-btn {
    border-left: 1px solid #e9ecef;
    border-radius: 0 8px 8px 0;
}

.timeline-side-btn:hover {
    background: #e9ecef;
    border-color: #adb5bd;
    color: #495057;
}

.timeline-side-btn:disabled {
    opacity: 0.3;
    cursor: not-allowed;
    border-color: #ddd;
    color: #ccc;
}

.timeline-side-btn:disabled:hover {
    background: #f8f9fa;
    border-color: #ddd;
    color: #ccc;
}

.timeline-wrapper {
    flex: 1;
    height: 60px;
    background: #f8f9fa;
    border-radius: 0;
    position: relative;
    overflow: hidden;
    border: 1px solid #e9ecef;
    border-left: none;
    border-right: none;
}

.timeline-track {
    height: 100%;
    position: relative;
    display: flex;
    align-items: center;
    transition: transform 0.3s cubic-bezier(0.25, 0.46, 0.45, 0.94);
}

.timeline-segment {
    height: 24px;
    border-radius: 3px;
    margin: 0 1px;
    cursor: pointer;
    transition: all 0.2s ease;
    opacity: 0.8;
    position: absolute;
    top: 50%;
    transform: translateY(-50%);
}

.timeline-segment:hover {
    opacity: 1;
    transform: translateY(-50%) scaleY(1.2);
}

.timeline-segment.active {
    opacity: 1;
    transform: translateY(-50%) scaleY(1.3);
    box-shadow: 0 2px 8px rgba(0,0,0,0.2);
    z-index: 5;
}

.timeline-position-indicator {
    position: absolute;
    top: 50%;
    transform: translateY(-50%);
    width: 2px;
    height: 40px;
    background: #007bff;
    border-radius: 1px;
    z-index: 10;
    pointer-events: none;
}

.loading-spinner {
    position: absolute;
    top: 50%;
    left: 50%;
    transform: translate(-50%, -50%);
    z-index: 5;
}

.spinner-border {
    width: 24px;
    height: 24px;
    border: 2px solid #f3f3f3;
    border-top: 2px solid #007bff;
    border-radius: 50%;
    animation: spin 1s linear infinite;
}

@keyframes spin {
    0% { transform: rotate(0deg); }
    100% { transform: rotate(360deg); }
}

.app-legend {
    display: flex;
    flex-wrap: wrap;
    gap: 12px;
    margin-top: 20px;
    padding-top: 15px;
    border-top: 1px solid #e5e5e5;
}

.legend-item {
    display: flex;
    align-items: center;
    gap: 6px;
    font-size: 12px;
    color: #666;
}

.legend-color {
    width: 12px;
    height: 12px;
    border-radius: 2px;
}

/* Arrow icons using CSS */
.bi-chevron-left::before {
    content: "‹";
    font-size: 20px;
    font-weight: bold;
}

.bi-chevron-right::before {
    content: "›";
    font-size: 20px;
    font-weight: bold;
}

.bi-arrow-clockwise::before {
    content: "↻";
    font-size: 16px;
}

.app-legend {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-top: 15px;
}

.app-legend-item {
  display: flex;
  align-items: center;
  gap: 5px;
  padding: 4px 8px;
  background: white;
  border-radius: 4px;
  font-size: 0.85em;
  border: 1px solid #dee2e6;
}

.app-color-dot {
  width: 12px;
  height: 12px;
  border-radius: 50%;
}

.content-container {
  margin-top: 20px;
}

.image-container {
  text-align: center;
  margin-bottom: 20px;
  position: relative;
}

.image-container img {
  max-width: 100%;
  height: auto;
  border: 1px solid #ddd;
  border-radius: 8px;
  transition: opacity 0.3s ease;
}

.image-loading {
  opacity: 0.7;
}

.entry-info {
  background: white;
  padding: 20px;
  border-radius: 8px;
  border: 1px solid #dee2e6;
  box-shadow: 0 2px 5px rgba(0,0,0,0.05);
}

.entry-info h5 {
  color: #495057;
  margin-bottom: 15px;
  display: flex;
  align-items: center;
  gap: 8px;
}

.info-item {
  margin-bottom: 10px;
}

.info-label {
  font-weight: bold;
  color: #6c757d;
}

.text-content {
  background: #f8f9fa;
  padding: 15px;
  border-radius: 4px;
  border: 1px solid #e9ecef;
  max-height: 300px;
  overflow-y: auto;
  font-family: 'Consolas', 'Monaco', monospace;
  font-size: 0.95em;
  line-height: 1.5;
  white-space: pre-wrap;
  word-break: break-word;
}

.text-content-preview {
  max-height: 120px;
  overflow: hidden;
  position: relative;
}

.text-content-full {
  max-height: none;
}

.text-expand-btn {
  display: block;
  width: 100%;
  text-align: center;
  margin-top: 5px;
  padding: 4px;
  background: #f8f9fa;
  border: 1px solid #dee2e6;
  border-radius: 0 0 4px 4px;
  cursor: pointer;
  color: #007bff;
  font-size: 0.9em;
}

.text-content-fade {
  position: absolute;
  bottom: 0;
  left: 0;
  width: 100%;
  height: 40px;
  background: linear-gradient(to bottom, rgba(248,249,250,0), rgba(248,249,250,1));
  pointer-events: none;
}

.text-content-wrapper {
  position: relative;
}

.copy-btn {
  position: absolute;
  top: 10px;
  right: 10px;
  background: #fff;
  border: 1px solid #dee2e6;
  border-radius: 4px;
  padding: 3px 8px;
  font-size: 0.8em;
  cursor: pointer;
  z-index: 10;
}

.copy-btn:hover {
  background: #f8f9fa;
}

.loading-spinner {
  display: none;
  position: absolute;
  top: 50%;
  left: 50%;
  transform: translate(-50%, -50%);
  z-index: 100;
}

.current-time {
  font-size: 1.1em;
  font-weight: 500;
  color: #495057;
}

.timeline-stats {
  font-size: 0.9em;
  color: #6c757d;
}

@media (max-width: 768px) {
  .date-selector-container {
    flex-direction: column;
    align-items: stretch;
    gap: 15px;
  }
  
  .date-controls {
    justify-content: center;
  }
  
  .date-selector {
    min-width: auto;
    max-width: none;
  }
  
  .timeline-info {
    flex-direction: column;
    gap: 10px;
    align-items: stretch;
  }
  
  .timeline-controls {
    justify-content: center;
  }
  
  .app-legend {
    justify-content: center;
  }
  
  .entry-info {
    margin-top: 15px;
  }
}
</style>

<script>
// Recording Controller Class
class RecordingController {
  constructor() {
    this.isRecording = true;
    this.isPaused = false;
    this.sessionStartTime = Date.now();
    this.screenshotCount = 0;
    
    this.initializeElements();
    this.bindEvents();
    this.startStatusUpdates();
    this.updateInitialStats();

    this.checkRecordingState();
  }
  
  initializeElements() {
    this.recordingIndicator = document.getElementById('recordingIndicator');
    this.recordingText = document.getElementById('recordingText');
    this.recordingStats = document.getElementById('recordingStats');
    this.pauseBtn = document.getElementById('pauseBtn');
    this.resumeBtn = document.getElementById('resumeBtn');
    this.settingsBtn = document.getElementById('settingsBtn');
    this.screenshotCountEl = document.getElementById('screenshotCount');
    this.sessionDurationEl = document.getElementById('sessionDuration');
    this.controlContainer = document.querySelector('.recording-control-container');
    this.recordingDot = document.querySelector('.recording-dot');
  }
  
  bindEvents() {
    this.pauseBtn.addEventListener('click', () => this.pauseRecording());
    this.resumeBtn.addEventListener('click', () => this.resumeRecording());
    this.settingsBtn.addEventListener('click', () => this.openSettings());
    
    // Keyboard shortcuts
    document.addEventListener('keydown', (e) => {
      // Don't trigger if user is typing in an input
      if (e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA') return;
      
      // Space bar to pause/resume
      if (e.code === 'Space' && (e.ctrlKey || e.metaKey)) {
        e.preventDefault();
        this.toggleRecording();
      }
    });
  }
  
  async pauseRecording() {
    if (this.isPaused) return;
    
    try {
      const response = await fetch('/api/recording/pause', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' }
      });
      
      if (response.ok) {
        this.isPaused = true;
        this.updateUI();
        this.showNotification('Recording paused', 'warning');
      } else {
        throw new Error('Failed to pause recording');
      }
    } catch (error) {
      console.error('Error pausing recording:', error);
      this.showNotification('Failed to pause recording', 'error');
    }
  }

  async checkRecordingState() {
    try {
      const response = await fetch('/api/recording/status');
      if (response.ok) {
        const data = await response.json();
        
        // Update local state to match server state
        this.isPaused = data.is_paused || false;
        this.isRecording = data.is_recording || false;
        
        // Update UI to match actual state
        this.updateUI();
        
        console.log('Recording state loaded:', data);
      }
    } catch (error) {
      console.error('Error checking recording state:', error);
    }
  }
  
  async resumeRecording() {
    if (!this.isPaused) return;
    
    try {
      const response = await fetch('/api/recording/resume', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' }
      });
      
      if (response.ok) {
        this.isPaused = false;
        this.updateUI();
        this.showNotification('Recording resumed', 'success');
      } else {
        throw new Error('Failed to resume recording');
      }
    } catch (error) {
      console.error('Error resuming recording:', error);
      this.showNotification('Failed to resume recording', 'error');
    }
  }
  
  toggleRecording() {
    if (this.isPaused) {
      this.resumeRecording();
    } else {
      this.pauseRecording();
    }
  }
  
  updateUI() {
    if (this.isPaused) {
      // Paused state
      this.pauseBtn.style.display = 'none';
      this.resumeBtn.style.display = 'flex';
      this.recordingText.textContent = 'Paused';
      this.recordingDot.classList.add('paused');
      this.controlContainer.classList.add('paused');
    } else {
      // Recording state
      this.pauseBtn.style.display = 'flex';
      this.resumeBtn.style.display = 'none';
      this.recordingText.textContent = 'Recording';
      this.recordingDot.classList.remove('paused');
      this.controlContainer.classList.remove('paused');
    }
  }
  
  startStatusUpdates() {
    // Update session duration every second
    setInterval(() => {
      this.updateSessionDuration();
    }, 1000);
    
    // Update screenshot count every 10 seconds
    setInterval(() => {
      this.updateScreenshotCount();
    }, 10000);
  }
  
  updateSessionDuration() {
    const elapsed = Math.floor((Date.now() - this.sessionStartTime) / 1000);
    const hours = Math.floor(elapsed / 3600);
    const minutes = Math.floor((elapsed % 3600) / 60);
    const seconds = elapsed % 60;
    
    let duration;
    if (hours > 0) {
      duration = `${hours}:${minutes.toString().padStart(2, '0')}:${seconds.toString().padStart(2, '0')}`;
    } else {
      duration = `${minutes}:${seconds.toString().padStart(2, '0')}`;
    }
    
    this.sessionDurationEl.textContent = duration;
  }
  
  async updateScreenshotCount() {
    try {
      const response = await fetch('/api/recording/stats');
      if (response.ok) {
        const data = await response.json();
        this.screenshotCount = data.screenshot_count || 0;
        this.screenshotCountEl.textContent = this.screenshotCount.toLocaleString();
      }
    } catch (error) {
      console.error('Error fetching screenshot count:', error);
    }
  }
  
  async updateInitialStats() {
    await this.updateScreenshotCount();
  }
  
  openSettings() {
    console.log('Settings modal would open here');
    this.showNotification('Settings panel coming soon', 'info');
  }
  
  showNotification(message, type = 'info') {
    // Simple notification for now
    const notification = document.createElement('div');
    notification.textContent = message;
    notification.style.cssText = `
      position: fixed;
      bottom: 20px;
      right: 20px;
      background: white;
      border: 1px solid #dee2e6;
      border-radius: 8px;
      padding: 12px 16px;
      box-shadow: 0 4px 12px rgba(0,0,0,0.15);
      z-index: 1000;
      font-size: 14px;
      color: #495057;
    `;
    
    document.body.appendChild(notification);
    
    // Auto-remove after 3 seconds
    setTimeout(() => {
      if (notification.parentNode) {
        notification.parentNode.removeChild(notification);
      }
    }, 3000);
  }
}

// Initialize everything when DOM is ready
document.addEventListener('DOMContentLoaded', () => {
  // Initialize recording controller
  window.recordingController = new RecordingController();
  
  // Initialize timeline (your existing timeline code)
  window.timeline = new DayTimeline();
  
  // Auto-refresh current day every 30 seconds
  setInterval(() => {
    if (!window.timeline.isLoading && !window.timeline.isDragging) {
      window.timeline.refreshCurrentDay();
    }
  }, 30000);
});

class DayTimeline {
  constructor() {
    this.currentIndex = 0;
    this.dayEntries = [];
    this.appColors = {};
    this.selectedDate = null;
    this.availableDates = [];
    this.isLoading = false;
    this.isDragging = false;
    this.dragStartX = 0;
    this.trackOffset = 0;
    this.segmentWidth = 12;
    
    this.initializeElements();
    this.bindEvents();
    this.loadAvailableDates();
  }
  
  initializeElements() {
    this.timelineTrack = document.getElementById('timelineTrack');
    this.timelineWrapper = document.getElementById('timelineWrapper');
    this.positionIndicator = document.getElementById('positionIndicator');
    this.currentTimeEl = document.getElementById('currentTime');
    this.timelineStatsEl = document.getElementById('timelineStats');
    this.appLegendEl = document.getElementById('appLegend');
    this.timestampImage = document.getElementById('timestampImage');
    this.imageSpinner = document.getElementById('imageSpinner');
    this.entryDetails = document.getElementById('entryDetails');
    this.prevBtn = document.getElementById('prevBtn');
    this.nextBtn = document.getElementById('nextBtn');
    this.refreshBtn = document.getElementById('refreshBtn');
    this.dateSelector = document.getElementById('dateSelector');
    this.prevDayBtn = document.getElementById('prevDayBtn');
    this.nextDayBtn = document.getElementById('nextDayBtn');
  }
  
  bindEvents() {
    this.prevBtn.addEventListener('click', () => this.navigateToIndex(this.currentIndex - 1));
    this.nextBtn.addEventListener('click', () => this.navigateToIndex(this.currentIndex + 1));
    this.refreshBtn.addEventListener('click', () => this.refreshCurrentDay());
    
    this.dateSelector.addEventListener('change', (e) => this.loadDay(e.target.value));
    this.prevDayBtn.addEventListener('click', () => this.navigateDays(-1));
    this.nextDayBtn.addEventListener('click', () => this.navigateDays(1));
    
    document.addEventListener('keydown', (e) => {
      if (e.target.tagName === 'INPUT') return;
      
      switch(e.key) {
        case 'ArrowLeft':
          e.preventDefault();
          this.navigateToIndex(this.currentIndex - 1);
          break;
        case 'ArrowRight':
          e.preventDefault();
          this.navigateToIndex(this.currentIndex + 1);
          break;
        case 'Home':
          e.preventDefault();
          this.navigateToIndex(0);
          break;
        case 'End':
          e.preventDefault();
          this.navigateToIndex(this.dayEntries.length - 1);
          break;
        case 'PageUp':
          e.preventDefault();
          this.navigateDays(-1);
          break;
        case 'PageDown':
          e.preventDefault();
          this.navigateDays(1);
          break;
      }
    });
    
    this.timelineTrack.addEventListener('click', (e) => {
      if (e.target.classList.contains('timeline-segment')) {
        const index = parseInt(e.target.dataset.index);
        if (!isNaN(index)) {
          this.navigateToIndex(index);
        }
      }
    });
    
    this.timelineWrapper.addEventListener('mousedown', (e) => this.handleDragStart(e));
    document.addEventListener('mousemove', (e) => this.handleDragMove(e));
    document.addEventListener('mouseup', () => this.handleDragEnd());
    
    this.timelineWrapper.addEventListener('touchstart', (e) => {
      e.preventDefault();
      this.handleDragStart(e.touches[0]);
    });
    document.addEventListener('touchmove', (e) => {
      if (this.isDragging) {
        e.preventDefault();
        this.handleDragMove(e.touches[0]);
      }
    });
    document.addEventListener('touchend', () => this.handleDragEnd());
    
    this.timelineWrapper.addEventListener('contextmenu', (e) => e.preventDefault());
    
    window.addEventListener('resize', () => {
      this.centerCurrentSegment();
    });
  }
  
  async loadAvailableDates() {
    this.showLoading();
    try {
      const response = await fetch('/api/available-dates');
      if (!response.ok) {
        throw new Error(`HTTP ${response.status}: ${response.statusText}`);
      }
      
      const data = await response.json();
      if (data.error) {
        throw new Error(data.error);
      }
      
      this.availableDates = data.dates || [];
      this.populateDateSelector();
      
      if (this.availableDates.length > 0) {
        await this.loadDay(this.availableDates[0]);
      } else {
        this.showEmptyState();
      }
    } catch (error) {
      console.error('Error loading available dates:', error);
      this.showError(error.message);
    } finally {
      this.hideLoading();
    }
  }
  
  populateDateSelector() {
    this.dateSelector.innerHTML = '';
    
    this.availableDates.forEach(date => {
      const option = document.createElement('option');
      option.value = date;
      option.textContent = this.formatDateForDisplay(date);
      this.dateSelector.appendChild(option);
    });
  }
  
  formatDateForDisplay(dateString) {
    const date = new Date(dateString);
    const today = new Date();
    const yesterday = new Date(today);
    yesterday.setDate(yesterday.getDate() - 1);
    
    if (date.toDateString() === today.toDateString()) {
      return 'Today';
    } else if (date.toDateString() === yesterday.toDateString()) {
      return 'Yesterday';
    } else {
      return date.toLocaleDateString('en-US', { 
        weekday: 'short', 
        month: 'short', 
        day: 'numeric',
        year: date.getFullYear() !== today.getFullYear() ? 'numeric' : undefined
      });
    }
  }
  
  async loadDay(dateString) {
    if (!dateString || this.isLoading) return;
    
    this.showLoading();
    this.selectedDate = dateString;
    
    try {
      const response = await fetch(`/api/day-entries?date=${encodeURIComponent(dateString)}`);
      if (!response.ok) {
        throw new Error(`HTTP ${response.status}: ${response.statusText}`);
      }
      
      const data = await response.json();
      if (data.error) {
        throw new Error(data.error);
      }
      
      this.dayEntries = data.entries || [];
      this.appColors = data.app_colors || {};
      
      if (this.dayEntries.length > 0) {
        this.renderTimeline();
        this.navigateToIndex(0);
        this.updateStats();
        this.updateDateNavigation();
      } else {
        this.showEmptyDay();
      }
      
    } catch (error) {
      console.error('Error loading day entries:', error);
      this.showError(error.message);
    } finally {
      this.hideLoading();
    }
  }
  
  renderTimeline() {
    this.timelineTrack.innerHTML = '';
    
    if (this.dayEntries.length === 0) return;
    
    this.dayEntries.forEach((entry, index) => {
      const segment = document.createElement('div');
      segment.className = 'timeline-segment';
      segment.style.backgroundColor = this.appColors[entry.app] || this.appColors['Unknown'] || '#9E9E9E';
      segment.style.width = this.segmentWidth + 'px';
      segment.title = entry.app + ' - ' + new Date(entry.timestamp * 1000).toLocaleString();
      segment.dataset.index = index;
      segment.dataset.timestamp = entry.timestamp;
      
      const positionFromEnd = this.dayEntries.length - 1 - index;
      segment.style.left = (positionFromEnd * (this.segmentWidth + 2)) + 'px';
      segment.style.position = 'absolute';
      
      this.timelineTrack.appendChild(segment);
    });
    
    const totalWidth = this.dayEntries.length * (this.segmentWidth + 2);
    this.timelineTrack.style.width = totalWidth + 'px';
    this.timelineTrack.style.position = 'relative';
    
    this.renderAppLegend();
  }
  
  navigateToIndex(index) {
    if (index < 0 || index >= this.dayEntries.length) return;
    
    const previousActive = this.timelineTrack.querySelector('.timeline-segment.active');
    if (previousActive) {
      previousActive.classList.remove('active');
    }
    
    const newActive = this.timelineTrack.querySelector(`[data-index="${index}"]`);
    if (newActive) {
      newActive.classList.add('active');
    }
    
    this.currentIndex = index;
    this.updateContent();
    this.updatePositionIndicator();
    this.updateNavigationButtons();
    this.centerCurrentSegment();
  }
  
  centerCurrentSegment() {
    if (this.dayEntries.length === 0) return;
    
    const segment = this.timelineTrack.querySelector(`[data-index="${this.currentIndex}"]`);
    if (!segment) return;
    
    const wrapperWidth = this.timelineWrapper.offsetWidth;
    const wrapperCenter = wrapperWidth / 2;
    
    const positionFromEnd = this.dayEntries.length - 1 - this.currentIndex;
    const segmentLeft = positionFromEnd * (this.segmentWidth + 2);
    const segmentCenter = segmentLeft + (this.segmentWidth / 2);
    
    this.trackOffset = wrapperCenter - segmentCenter;
    
    this.timelineTrack.style.transition = 'transform 0.3s ease';
    this.timelineTrack.style.transform = `translateX(${this.trackOffset}px)`;
  }
  
  updateContent() {
    const entry = this.dayEntries[this.currentIndex];
    if (!entry) return;
    
    this.currentTimeEl.textContent = new Date(entry.timestamp * 1000).toLocaleString();
    
    this.timestampImage.style.display = 'none';
    this.imageSpinner.style.display = 'block';
    
    const img = new Image();
    img.onload = () => {
      this.timestampImage.src = img.src;
      this.timestampImage.style.display = 'block';
      this.imageSpinner.style.display = 'none';
    };
    img.onerror = () => {
      this.timestampImage.alt = 'Image not found';
      this.timestampImage.style.display = 'block';
      this.imageSpinner.style.display = 'none';
    };
    img.src = `/static/${entry.timestamp}.webp`;
    
    this.updateEntryDetails(entry);
  }
  
  updateEntryDetails(entry) {
    let textContentHtml = '';
    
    if (entry.text && entry.text.trim()) {
      const needsExpand = entry.text.length > 300;
      const escapedText = entry.text.replace(/\\\\/g, '\\\\\\\\').replace(/`/g, '\\\\`');
      
      textContentHtml = 
        '<div class="text-content-wrapper">' +
          '<div class="text-content ' + (needsExpand ? 'text-content-preview' : '') + '">' +
            entry.text +
            (needsExpand ? '<div class="text-content-fade"></div>' : '') +
          '</div>' +
          (needsExpand ? '<button class="text-expand-btn" onclick="toggleTextExpand(this)">Show More</button>' : '') +
          '<button class="markdown-btn" onclick="toggleMarkdownView(this, `' + escapedText + '`)">' +
            '<i class="bi bi-markdown"></i> Markdown' +
          '</button>' +
          '<button class="copy-btn" onclick="copyTextToClipboard(`' + escapedText + '`)">' +
            '<i class="bi bi-clipboard"></i> Copy' +
          '</button>' +
        '</div>';
    } else {
      textContentHtml = '<div class="text-muted">No text extracted</div>';
    }
    
    const color = this.appColors[entry.app] || this.appColors['Unknown'] || '#9E9E9E';
    
    this.entryDetails.innerHTML = 
      '<div class="info-item">' +
        '<span class="info-label">App:</span> ' +
        '<span style="color: ' + color + '">● ' + (entry.app || 'Unknown') + '</span>' +
      '</div>' +
      '<div class="info-item">' +
        '<span class="info-label">Title:</span> ' + (entry.title || 'No title') +
      '</div>' +
      '<div class="info-item">' +
        '<span class="info-label">Time:</span> ' + new Date(entry.timestamp * 1000).toLocaleString() +
      '</div>' +
      '<div class="info-item">' +
        '<span class="info-label">Position:</span> ' + (this.currentIndex + 1) + ' of ' + this.dayEntries.length +
        ' <small class="text-muted">(' + (this.currentIndex === 0 ? 'Latest' : this.currentIndex === this.dayEntries.length - 1 ? 'Oldest' : 'Middle') + ')</small>' +
      '</div>' +
      '<div class="info-item">' +
        '<span class="info-label">Extracted Text:</span>' + textContentHtml +
      '</div>';
  }
  
  updatePositionIndicator() {
    const wrapperCenter = this.timelineWrapper.offsetWidth / 2;
    this.positionIndicator.style.left = wrapperCenter + 'px';
  }
  
  updateNavigationButtons() {
    this.prevBtn.disabled = this.currentIndex <= 0;
    this.nextBtn.disabled = this.currentIndex >= this.dayEntries.length - 1;
    
    this.prevBtn.title = 'Newer (←)';
    this.nextBtn.title = 'Older (→)';
  }
  
  updateDateNavigation() {
    const currentDateIndex = this.availableDates.indexOf(this.selectedDate);
    this.prevDayBtn.disabled = currentDateIndex <= 0;
    this.nextDayBtn.disabled = currentDateIndex >= this.availableDates.length - 1;
    
    this.dateSelector.value = this.selectedDate;
  }
  
  navigateDays(direction) {
    const currentIndex = this.availableDates.indexOf(this.selectedDate);
    const newIndex = currentIndex + direction;
    
    if (newIndex >= 0 && newIndex < this.availableDates.length) {
      this.loadDay(this.availableDates[newIndex]);
    }
  }
  
  updateStats() {
    const uniqueApps = new Set(this.dayEntries.map(e => e.app)).size;
    const dateFormatted = this.formatDateForDisplay(this.selectedDate);
    this.timelineStatsEl.textContent = `${this.dayEntries.length} snapshots on ${dateFormatted} • ${uniqueApps} apps`;
  }
  
  renderAppLegend() {
  if (!this.appColors || Object.keys(this.appColors).length === 0) {
    this.appLegendEl.innerHTML = '<div class="text-muted">No apps detected</div>';
    return;
  }
  
  const apps = Object.keys(this.appColors).filter(app => app !== 'Unknown' && app !== null && app !== '');
  apps.sort();
  
  if (apps.length === 0) {
    this.appLegendEl.innerHTML = '<div class="text-muted">No apps detected</div>';
    return;
  }
  
  // Use the new legend-item and legend-color classes
  this.appLegendEl.innerHTML = apps.map(app => 
    '<div class="legend-item">' +
      '<div class="legend-color" style="background-color: ' + this.appColors[app] + '"></div>' +
      '<span>' + app + '</span>' +
    '</div>'
  ).join('');
}
  
  async refreshCurrentDay() {
    if (this.selectedDate) {
      await this.loadDay(this.selectedDate);
    }
  }
  
  handleDragStart(e) {
    this.isDragging = true;
    this.dragStartX = e.clientX;
    this.dragStartOffset = this.trackOffset;
    this.timelineWrapper.style.cursor = 'grabbing';
    this.timelineTrack.style.transition = 'none';
    document.body.style.userSelect = 'none';
  }
  
  handleDragMove(e) {
    if (!this.isDragging) return;
    
    const deltaX = e.clientX - this.dragStartX;
    const newOffset = this.dragStartOffset + deltaX;
    
    this.timelineTrack.style.transform = `translateX(${newOffset}px)`;
    this.updatePreviewDuringDrag(newOffset);
  }
  
  updatePreviewDuringDrag(currentOffset) {
    const wrapperCenter = this.timelineWrapper.offsetWidth / 2;
    let closestIndex = this.currentIndex;
    let minDistance = Infinity;
    
    for (let i = 0; i < this.dayEntries.length; i++) {
      const positionFromEnd = this.dayEntries.length - 1 - i;
      const segmentLeft = positionFromEnd * (this.segmentWidth + 2);
      const segmentCenter = segmentLeft + (this.segmentWidth / 2) + currentOffset;
      const distance = Math.abs(segmentCenter - wrapperCenter);
      
      if (distance < minDistance) {
        minDistance = distance;
        closestIndex = i;
      }
    }
    
    if (closestIndex !== this.currentIndex) {
      const previousActive = this.timelineTrack.querySelector('.timeline-segment.active');
      if (previousActive) {
        previousActive.classList.remove('active');
      }
      
      const newActive = this.timelineTrack.querySelector(`[data-index="${closestIndex}"]`);
      if (newActive) {
        newActive.classList.add('active');
      }
      
      this.currentIndex = closestIndex;
      
      const entry = this.dayEntries[closestIndex];
      if (entry) {
        this.currentTimeEl.textContent = new Date(entry.timestamp * 1000).toLocaleString();
        this.updateEntryDetails(entry);
      }
    }
  }
  
  handleDragEnd() {
    if (!this.isDragging) return;
    
    this.isDragging = false;
    this.timelineWrapper.style.cursor = 'grab';
    this.timelineTrack.style.transition = 'transform 0.3s ease';
    document.body.style.userSelect = '';
    
    this.centerCurrentSegment();
    this.updateContent();
    this.updateNavigationButtons();
  }
  
  showLoading() {
    const spinner = document.querySelector('.timeline-container .loading-spinner');
    if (spinner) {
      spinner.style.display = 'block';
    }
  }
  
  hideLoading() {
    const spinner = document.querySelector('.timeline-container .loading-spinner');
    if (spinner) {
      spinner.style.display = 'none';
    }
  }
  
  showEmptyState() {
    this.timelineStatsEl.textContent = 'No snapshots found.';
    this.currentTimeEl.textContent = 'No data available';
    this.entryDetails.innerHTML = '<div class="alert alert-info">No snapshots recorded yet.</div>';
    this.timelineTrack.innerHTML = '';
    this.appLegendEl.innerHTML = '<div class="text-muted">No data available</div>';
  }
  
  showEmptyDay() {
    this.timelineStatsEl.textContent = `No snapshots found for ${this.formatDateForDisplay(this.selectedDate)}.`;
    this.currentTimeEl.textContent = 'No data for this day';
    this.entryDetails.innerHTML = '<div class="alert alert-info">No snapshots recorded on this day.</div>';
    this.timelineTrack.innerHTML = '';
    this.appLegendEl.innerHTML = '<div class="text-muted">No apps for this day</div>';
    this.updateDateNavigation();
  }
  
  showError(message) {
    this.timelineStatsEl.textContent = 'Error loading timeline data';
    this.currentTimeEl.textContent = 'Error';
    this.entryDetails.innerHTML = '<div class="alert alert-danger">Error loading timeline: ' + message + '</div>';
    this.timelineTrack.innerHTML = '';
    this.appLegendEl.innerHTML = '<div class="text-danger">Error loading apps</div>';
  }
}

// Initialize timeline when DOM is ready
document.addEventListener('DOMContentLoaded', () => {
  window.timeline = new DayTimeline();
  
  // Auto-refresh current day every 30 seconds
  setInterval(() => {
    if (!window.timeline.isLoading && !window.timeline.isDragging) {
      window.timeline.refreshCurrentDay();
    }
  }, 30000);
});

// Helper functions
function toggleTextExpand(btnElement) {
  const textContainer = btnElement.previousElementSibling;
  const fadeElement = textContainer.querySelector('.text-content-fade');
  
  if (textContainer.classList.contains('text-content-preview')) {
    textContainer.classList.remove('text-content-preview');
    textContainer.classList.add('text-content-full');
    btnElement.textContent = 'Show Less';
    if (fadeElement) fadeElement.style.display = 'none';
  } else {
    textContainer.classList.remove('text-content-full');
    textContainer.classList.add('text-content-preview');
    btnElement.textContent = 'Show More';
    if (fadeElement) fadeElement.style.display = 'block';
  }
}

function copyTextToClipboard(textContent) {
  navigator.clipboard.writeText(textContent).then(function() {
    const toast = document.createElement('div');
    toast.textContent = 'Text copied to clipboard!';
    toast.style.cssText = 'position: fixed; bottom: 20px; right: 20px; background: #28a745; color: white; padding: 12px 20px; border-radius: 4px; z-index: 1000; font-size: 14px; box-shadow: 0 2px 10px rgba(0,0,0,0.2);';
    document.body.appendChild(toast);
    
    setTimeout(() => {
      document.body.removeChild(toast);
    }, 2000);
  }, function(err) {
    console.error('Could not copy text: ', err);
    alert('Failed to copy text to clipboard');
  });
}
</script>
{% endblock %}
"""
    )

@app.route("/api/markdown-convert", methods=["POST"])
def convert_markdown():
    """Convert text to markdown HTML"""
    try:
        data = request.get_json()
        text = data.get('text', '')
        
        if not text:
            return jsonify({'error': 'No text provided'}), 400
        
        # Convert markdown to HTML
        html = markdown.markdown(text, extensions=['extra', 'codehilite'])
        
        return jsonify({'html': html})
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# Update the existing API route with improved page size
# Remove the duplicate @app.route("/api/timeline-data") - keep only one version
@app.route("/api/timeline-data")
def timeline_data():
    """API endpoint to get timeline data with pagination"""
    try:
        page = int(request.args.get('page', 0))
        page_size = int(request.args.get('page_size', 1000))
        
        entries = get_all_entries()
        timestamps = get_timestamps()
        
        if not entries:
            return jsonify({
                'entries': {},
                'app_colors': {},
                'timestamps': [],
                'total_count': 0,
                'has_more': False
            })
        
        # Sort entries by timestamp (newest first)
        entries.sort(key=lambda x: x.timestamp, reverse=True)
        
        # Calculate pagination
        start_idx = page * page_size
        end_idx = start_idx + page_size
        paged_entries = entries[start_idx:end_idx]
        
        # Create entry map for paged entries
        entry_map = {}
        for entry in paged_entries:
            entry_map[str(entry.timestamp)] = {
                'app': entry.app or 'Unknown',
                'title': entry.title or 'No title', 
                'text': entry.text or '',
                'timestamp': entry.timestamp
            }
        
        # Get app color mapping based on all entries (not just paged)
        app_colors = get_app_color_mapping(entries)
        
        return jsonify({
            'entries': entry_map,
            'app_colors': app_colors,
            'timestamps': [entry.timestamp for entry in paged_entries],
            'total_count': len(entries),
            'has_more': end_idx < len(entries)
        })
        
    except Exception as e:
        print(f"API Error: {e}")
        return jsonify({'error': str(e)}), 500


@app.route("/api/recording/pause", methods=["POST"])
def pause_recording():
    """Pause recording"""
    try:
        success = recording_controller.pause()
        if success:
            return jsonify({
                'success': True, 
                'message': 'Recording paused',
                'state': recording_controller.get_state()
            })
        else:
            return jsonify({
                'success': False,
                'message': 'Recording was already paused',
                'state': recording_controller.get_state()
            })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route("/api/recording/resume", methods=["POST"]) 
def resume_recording():
    """Resume recording"""
    try:
        success = recording_controller.resume()
        if success:
            return jsonify({
                'success': True, 
                'message': 'Recording resumed',
                'state': recording_controller.get_state()
            })
        else:
            return jsonify({
                'success': False,
                'message': 'Recording was already active',
                'state': recording_controller.get_state()
            })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route("/api/recording/status")
def recording_status():
    """Get recording status"""
    try:
        return jsonify(recording_controller.get_state())
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route("/api/recording/stats")
def recording_stats():
    """Get recording stats"""
    try:
        entries = get_all_entries()
        today = datetime.now().date()
        today_entries = [
            entry for entry in entries 
            if datetime.fromtimestamp(entry.timestamp).date() == today
        ]
        
        state = recording_controller.get_state()
        return jsonify({
            'screenshot_count': len(entries),
            'today_count': len(today_entries),
            'is_recording': state['is_recording'],
            'is_paused': state['is_paused'],
            'session_start_time': state['session_start_time'],
            'total_screenshots': len(entries)
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route("/search")
def search():
    q = request.args.get("q")
    if not q:
        return redirect("/")

    entries = get_all_entries()

    try:
        query_embedding = get_embedding(q)
    except Exception as e:
        return render_template_string(
            """
{% extends "base_template" %}
{% block content %}
    <div class="container">
        <div class="alert alert-danger" role="alert">
            Error generating embedding for query: {{ error }}
        </div>
    </div>
{% endblock %}
""",
            entries=[],
            query=q,
            error=str(e)
        )

    # Filter out entries with mismatched embedding dimensions and handle safely
    valid_entries = []
    valid_embeddings = []

    for entry in entries:
        try:
            emb = np.frombuffer(entry.embedding, dtype=np.float64)
            if emb.shape[0] == query_embedding.shape[0]:
                valid_entries.append(entry)
                valid_embeddings.append(emb)
        except Exception as e:
            print(f"Skipping entry with corrupted embedding: {e}")
            continue

    if not valid_embeddings:
        return render_template_string(
            """
{% extends "base_template" %}
{% block content %}
    <div class="container">
        <div class="alert alert-info" role="alert">
            No matching entries found. Try a different search term.
        </div>
    </div>
{% endblock %}
""",
            entries=[],
            query=q
        )

    similarities = [cosine_similarity(query_embedding, emb) for emb in valid_embeddings]

    # Combine entries and similarities, sort by similarity and timestamp (desc)
    scored_entries = [(valid_entries[i], similarities[i]) for i in range(len(valid_entries))]
    scored_entries.sort(key=lambda x: (x[1], x[0].timestamp), reverse=True)
    sorted_entries = [entry for entry, _ in scored_entries]

    # Pagination setup
    page = int(request.args.get("page", 1))
    page_size = 10
    start = (page - 1) * page_size
    end = start + page_size
    paged_entries = sorted_entries[start:end]
    total_pages = (len(sorted_entries) + page_size - 1) // page_size

    return render_template_string(
        """
{% extends "base_template" %}
{% block content %}
    <div class="container">
        <div class="mb-3">
            <h4>Search Results for: "{{ query }}"</h4>
            <small class="text-muted">{{ entries|length }} results shown (page {{ page }} of {{ total_pages }})</small>
        </div>
        <div class="row">
            {% for entry in entries %}
                <div class="col-md-6 col-lg-4 mb-4">
                    <div class="card h-100">
                        <a href="#" data-toggle="modal" data-target="#modal-{{ loop.index0 }}">
                            <img src="/static/{{ entry['timestamp'] }}.webp" alt="Image" class="card-img-top" style="height: 200px; object-fit: cover;">
                        </a>
                        <div class="card-body">
                            <h6 class="card-title">{{ entry['app'] or 'Unknown App' }}</h6>
                            <p class="card-text">
                                <small class="text-muted">{{ entry['title'] or 'No title' }}</small><br>
                                <small>{{ entry['timestamp'] | timestamp_to_human_readable }}</small>
                            </p>
                            {% if entry['text'] %}
                            <p class="card-text">
                                <div class="search-card-text">{{ entry['text'] }}</div>
                                {% if entry['text']|length > 100 %}
                                <small class="text-primary mt-1" style="cursor: pointer;" data-toggle="modal" data-target="#modal-{{ loop.index0 }}">
                                    View full text...
                                </small>
                                {% endif %}
                            </p>
                            {% endif %}
                        </div>
                    </div>
                </div>
                <div class="modal fade" id="modal-{{ loop.index0 }}" tabindex="-1" role="dialog" aria-labelledby="modalLabel-{{ loop.index0 }}" aria-hidden="true">
                    <div class="modal-dialog modal-xl" role="document" style="max-width: 95vw;">
                        <div class="modal-content" style="height: 90vh;">
                            <div class="modal-header">
                                <h5 class="modal-title" id="modalLabel-{{ loop.index0 }}">
                                    {{ entry['app'] or 'Unknown App' }} - {{ entry['title'] or 'No title' }}
                                </h5>
                                <button type="button" class="close" data-dismiss="modal" aria-label="Close">
                                    <span aria-hidden="true">&times;</span>
                                </button>
                            </div>
                            <div class="modal-body" style="padding: 0; height: calc(90vh - 120px);">
                                <div class="row h-100">
                                    <div class="col-md-8 h-100" style="padding: 0;">
                                        <img src="/static/{{ entry['timestamp'] }}.webp" alt="Image" style="width: 100%; height: 100%; object-fit: contain;">
                                    </div>
                                    <div class="col-md-4 h-100" style="padding: 20px; background: #f8f9fa; overflow-y: auto;">
                                        <h6><i class="bi bi-info-circle"></i> Entry Details</h6>
                                        <hr>
                                        <div class="mb-3">
                                            <strong>App:</strong><br>
                                            <span class="text-muted">{{ entry['app'] or 'N/A' }}</span>
                                        </div>
                                        <div class="mb-3">
                                            <strong>Title:</strong><br>
                                            <span class="text-muted">{{ entry['title'] or 'N/A' }}</span>
                                        </div>
                                        <div class="mb-3">
                                            <strong>Timestamp:</strong><br>
                                            <span class="text-muted">{{ entry['timestamp'] | timestamp_to_human_readable }}</span>
                                        </div>
                                        {% if entry['text'] %}
                                        <div class="mb-3">
                                            <strong>Extracted Text:</strong><br>
                                            <div class="position-relative">
                                                <div class="modal-text-content">{{ entry['text'] }}</div>
                                                <button class="copy-btn" onclick="copyTextToClipboard(`{{ entry['text']|replace('`', '\\`') }}`)">
                                                    <i class="bi bi-clipboard"></i> Copy
                                                </button>
                                            </div>
                                        </div>
                                        {% endif %}
                                    </div>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>
            {% endfor %}
        </div>

        {% if total_pages > 1 %}
{% set range_start = (page - 2 if page - 2 > 0 else 1) %}
{% set range_end = (page + 2 if page + 2 < total_pages else total_pages) + 1 %}
<nav aria-label="Pagination" class="my-4">
  <ul class="pagination justify-content-center">
    <li class="page-item {% if page == 1 %}disabled{% endif %}">
      <a class="page-link" href="/search?q={{ query }}&page={{ page - 1 }}" aria-label="Previous">
        <span aria-hidden="true">&laquo;</span>
        <span class="sr-only">Previous</span>
      </a>
    </li>

    {% for p in range(range_start, range_end) %}
    <li class="page-item {% if p == page %}active{% endif %}">
      <a class="page-link" href="/search?q={{ query }}&page={{ p }}">{{ p }}</a>
    </li>
    {% endfor %}

    <li class="page-item {% if page == total_pages %}disabled{% endif %}">
      <a class="page-link" href="/search?q={{ query }}&page={{ page + 1 }}" aria-label="Next">
        <span aria-hidden="true">&raquo;</span>
        <span class="sr-only">Next</span>
      </a>
    </li>
  </ul>
</nav>
{% endif %}

    </div>
{% endblock %}
""",
        entries=paged_entries,
        query=q,
        page=page,
        total_pages=total_pages
    )


@app.route("/static/<filename>")
def serve_image(filename):
    import os
    # Try the exact filename first
    if os.path.exists(os.path.join(screenshots_path, filename)):
        return send_from_directory(screenshots_path, filename)
    
    # If not found, try with monitor indices (_0, _1, etc.)
    base_name = filename.rsplit('.', 1)[0]  # Remove extension
    extension = filename.rsplit('.', 1)[1] if '.' in filename else 'webp'
    
    # Try monitor indices 0, 1, 2 (covers most multi-monitor setups)
    for i in range(3):
        monitor_filename = f"{base_name}_{i}.{extension}"
        if os.path.exists(os.path.join(screenshots_path, monitor_filename)):
            return send_from_directory(screenshots_path, monitor_filename)
    
    # If still not found, return 404
    from flask import abort
    abort(404)


if __name__ == "__main__":
    create_db()

    print(f"Appdata folder: {appdata_folder}")
    print(f"Screenshots path: {screenshots_path}")
    if args.storage_path:
        print(f"Using custom storage path: {args.storage_path}")

    # Start the thread to record screenshots
    t = Thread(target=record_screenshots_thread)
    t.start()

    print(f"Starting OpenRecall web interface on http://{args.host}:{args.port}")
    app.run(host=args.host, port=args.port)