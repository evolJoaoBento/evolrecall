#!/usr/bin/env python3
"""
Database Viewer Interface - Property-Based Schema
Web interface to view and manage OpenRecall and Documentation databases
"""

import json
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path
from flask import Flask, render_template_string, request, jsonify
import os
import configparser
import shutil

HTML_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <title>OpenRecall Database Viewer</title>
    <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/bootstrap-icons@1.11.0/font/bootstrap-icons.css">
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }
        
        body { 
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; 
            background: #f8f9fa; 
            color: #495057;
            line-height: 1.6;
        }
        
        .header { 
            background: white; 
            padding: 20px; 
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
            border-bottom: 1px solid #dee2e6;
        }
        
        .header h1 { 
            margin: 0; 
            color: #495057;
            font-size: 1.5rem;
            font-weight: 600;
        }
        
        .header p {
            margin: 5px 0 0 0;
            color: #6c757d;
            font-size: 0.9rem;
        }
        
        .container { 
            padding: 20px;
            max-width: 1400px;
            margin: 0 auto;
        }
        
        /* Tabs */
        .tabs { 
            display: flex; 
            gap: 2px; 
            margin-bottom: 20px; 
            background: white; 
            padding: 8px; 
            border-radius: 12px; 
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
        }
        
        .tab { 
            padding: 12px 20px; 
            background: transparent; 
            border: none; 
            border-radius: 8px; 
            cursor: pointer; 
            font-weight: 500; 
            font-size: 0.95rem;
            color: #6c757d;
            transition: all 0.2s ease;
            display: flex;
            align-items: center;
            gap: 8px;
        }
        
        .tab i {
            font-size: 1rem;
        }
        
        .tab:hover:not(.active) {
            background: #f8f9fa;
            color: #495057;
        }
        
        .tab.active { 
            background: #007bff; 
            color: white; 
            box-shadow: 0 2px 8px rgba(0,123,255,0.3);
        }
        
        /* Table Container */
        .table-container { 
            background: white; 
            border-radius: 12px; 
            padding: 20px; 
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
            border: 1px solid #dee2e6;
            margin-bottom: 20px;
        }
        
        .table-header { 
            display: flex; 
            justify-content: space-between; 
            align-items: center; 
            margin-bottom: 20px; 
            padding-bottom: 15px;
            border-bottom: 1px solid #f1f3f4;
        }
        
        .table-title { 
            font-size: 1.25rem; 
            font-weight: 600; 
            color: #495057; 
        }
        
        /* Controls */
        .controls { 
            display: flex; 
            gap: 12px; 
            margin-bottom: 20px; 
            flex-wrap: wrap; 
            align-items: center;
        }
        
        .search-box { 
            flex: 1; 
            min-width: 250px; 
            padding: 12px 16px; 
            border: 1px solid #dee2e6; 
            border-radius: 8px; 
            font-size: 0.95rem;
            background: #f8f9fa;
            transition: all 0.2s ease;
        }
        
        .search-box:focus {
            outline: none;
            border-color: #007bff;
            background: white;
            box-shadow: 0 0 0 3px rgba(0,123,255,0.1);
        }
        
        .filter-select { 
            padding: 12px 16px; 
            border: 1px solid #dee2e6; 
            border-radius: 8px; 
            min-width: 140px; 
            background: #f8f9fa;
            font-size: 0.95rem;
            cursor: pointer;
            transition: all 0.2s ease;
        }
        
        .filter-select:focus {
            outline: none;
            border-color: #007bff;
            background: white;
            box-shadow: 0 0 0 3px rgba(0,123,255,0.1);
        }
        
        .btn { 
            padding: 12px 20px; 
            background: #007bff; 
            color: white; 
            border: none; 
            border-radius: 8px; 
            cursor: pointer; 
            font-weight: 500; 
            font-size: 0.95rem;
            transition: all 0.2s ease;
            display: inline-flex;
            align-items: center;
            gap: 6px;
        }
        
        .btn:hover { 
            background: #0056b3; 
            transform: translateY(-1px);
            box-shadow: 0 4px 12px rgba(0,123,255,0.3);
        }
        
        .btn-secondary { 
            background: #6c757d; 
        }
        
        .btn-secondary:hover { 
            background: #545b62; 
        }
        
        /* Table */
        table { 
            width: 100%; 
            border-collapse: collapse; 
            font-size: 0.95rem;
        }
        
        th { 
            background: #f8f9fa; 
            padding: 16px 12px; 
            text-align: left; 
            font-weight: 600; 
            color: #495057; 
            border-bottom: 1px solid #dee2e6;
            font-size: 0.9rem;
            text-transform: uppercase;
            letter-spacing: 0.5px;
        }
        
        td { 
            padding: 16px 12px; 
            border-bottom: 1px solid #f1f3f4; 
            vertical-align: top;
        }
        
        tr:hover { 
            background: #f8f9fa; 
        }
        
        tr:last-child td {
            border-bottom: none;
        }
        
        /* Pagination */
        .pagination { 
            display: flex; 
            justify-content: center; 
            gap: 8px; 
            margin-top: 30px; 
        }
        
        .page-btn { 
            padding: 10px 16px; 
            background: white; 
            border: 1px solid #dee2e6; 
            border-radius: 8px; 
            cursor: pointer; 
            font-size: 0.9rem;
            font-weight: 500;
            color: #495057;
            transition: all 0.2s ease;
        }
        
        .page-btn.active { 
            background: #007bff; 
            color: white; 
            border-color: #007bff; 
            box-shadow: 0 2px 8px rgba(0,123,255,0.3);
        }
        
        .page-btn:hover:not(.active) { 
            background: #f8f9fa; 
            border-color: #007bff;
            color: #007bff;
        }
        
        /* Stats */
        .stats { 
            display: grid; 
            grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); 
            gap: 20px; 
            margin-bottom: 30px; 
        }
        
        .stat-card { 
            background: white; 
            padding: 24px 20px; 
            border-radius: 12px; 
            text-align: center; 
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
            border: 1px solid #dee2e6;
            transition: transform 0.2s ease;
        }
        
        .stat-card:hover {
            transform: translateY(-2px);
            box-shadow: 0 4px 20px rgba(0,0,0,0.15);
        }
        
        .stat-number { 
            font-size: 2rem; 
            font-weight: 700; 
            color: #007bff; 
            line-height: 1;
        }
        
        .stat-label { 
            color: #6c757d; 
            margin-top: 8px; 
            font-size: 0.9rem;
            font-weight: 500;
        }
        
        /* Tab Content */
        .tab-content { display: none; }
        .tab-content.active { display: block; }
        
        /* Modal */
        .modal { 
            display: none; 
            position: fixed; 
            z-index: 1000; 
            left: 0; 
            top: 0; 
            width: 100%; 
            height: 100%; 
            background: rgba(0,0,0,0.5); 
            backdrop-filter: blur(4px);
        }
        
        .modal-content { 
            background: white; 
            margin: 50px auto; 
            padding: 30px; 
            width: 90%; 
            max-width: 900px; 
            border-radius: 12px; 
            max-height: 85vh; 
            overflow-y: auto; 
            box-shadow: 0 20px 60px rgba(0,0,0,0.3);
        }
        
        .modal-header { 
            display: flex; 
            justify-content: space-between; 
            align-items: center; 
            margin-bottom: 25px; 
            padding-bottom: 15px;
            border-bottom: 1px solid #f1f3f4;
        }
        
        .modal-title { 
            font-size: 1.5rem; 
            font-weight: 600; 
            color: #495057;
        }
        
        .close { 
            font-size: 1.5rem; 
            cursor: pointer; 
            color: #6c757d; 
            transition: color 0.2s ease;
            width: 40px;
            height: 40px;
            display: flex;
            align-items: center;
            justify-content: center;
            border-radius: 8px;
        }
        
        .close:hover { 
            color: #495057; 
            background: #f8f9fa;
        }
        
        /* Code block */
        .code-block { 
            background: #f8f9fa; 
            padding: 20px; 
            border-radius: 8px; 
            font-family: 'SF Mono', 'Monaco', 'Inconsolata', 'Roboto Mono', monospace; 
            font-size: 0.9rem;
            overflow-x: auto; 
            white-space: pre-wrap; 
            border: 1px solid #e9ecef;
            line-height: 1.5;
        }
        
        /* Truncate text */
        .truncate { 
            max-width: 300px; 
            white-space: nowrap; 
            overflow: hidden; 
            text-overflow: ellipsis; 
        }
        
        /* Tags */
        .tag { 
            display: inline-block; 
            background: #e9ecef; 
            color: #495057;
            padding: 4px 12px; 
            border-radius: 16px; 
            font-size: 0.8rem; 
            margin: 2px 4px 2px 0; 
            font-weight: 500;
            transition: all 0.2s ease;
        }
        
        .tag:hover {
            background: #dee2e6;
        }
        
        .tag.active { 
            background: #007bff; 
            color: white; 
        }
        
        /* Tree view */
        .tree { margin-left: 20px; }
        .tree-item { margin: 5px 0; padding: 5px; border-left: 2px solid #e0e0e0; }
        .tree-item:hover { background: #f8f9fa; }
        .tree-toggle { cursor: pointer; user-select: none; }
        .tree-children { margin-left: 15px; }
        
        /* Property path */
        .property-path { font-size: 12px; color: #666; font-style: italic; }
        
        /* Type badges */
        .type-badge { padding: 2px 6px; border-radius: 3px; font-size: 11px; font-weight: bold; text-transform: uppercase; }
        .type-text { background: #e3f2fd; color: #1565c0; }
        .type-json { background: #f3e5f5; color: #7b1fa2; }
        .type-file { background: #e8f5e8; color: #2e7d32; }
        .type-code { background: #fff3e0; color: #ef6c00; }
        .type-documentation { background: #e1f5fe; color: #0277bd; }
        .type-section { background: #fce4ec; color: #c2185b; }
        
        /* Settings form */
        .settings-form { 
            max-width: 700px; 
        }
        
        .form-group { 
            margin-bottom: 25px; 
        }
        
        .form-label { 
            display: block; 
            margin-bottom: 8px; 
            font-weight: 600; 
            color: #495057; 
            font-size: 0.95rem;
        }
        
        .form-input { 
            width: 100%; 
            padding: 12px 16px; 
            border: 1px solid #dee2e6; 
            border-radius: 8px; 
            font-size: 0.95rem; 
            transition: all 0.2s ease;
            background: #f8f9fa;
        }
        
        .form-input:focus { 
            border-color: #007bff; 
            outline: none; 
            box-shadow: 0 0 0 3px rgba(0,123,255,0.1);
            background: white;
        }
        
        .form-description { 
            font-size: 0.85rem; 
            color: #6c757d; 
            margin-top: 6px; 
            line-height: 1.4;
        }
        .btn-danger { 
            background: #dc3545; 
        }
        
        .btn-danger:hover { 
            background: #c82333; 
            transform: translateY(-1px);
            box-shadow: 0 4px 12px rgba(220,53,69,0.3);
        }
        
        .btn-success { 
            background: #28a745; 
        }
        
        .btn-success:hover { 
            background: #218838; 
            transform: translateY(-1px);
            box-shadow: 0 4px 12px rgba(40,167,69,0.3);
        }
        
        .alert { 
            padding: 16px 20px; 
            border-radius: 8px; 
            margin-bottom: 25px; 
            border: 1px solid transparent;
            font-size: 0.95rem;
        }
        
        .alert-success { 
            background: #d1e7dd; 
            color: #0a3622; 
            border-color: #a3cfbb; 
        }
        
        .alert-error { 
            background: #f8d7da; 
            color: #58151c; 
            border-color: #f1aeb5; 
        }
        .config-status { 
            display: inline-block; 
            padding: 6px 12px; 
            border-radius: 6px; 
            font-size: 0.8rem; 
            font-weight: 500;
        }
        
        .config-valid { 
            background: #d1e7dd; 
            color: #0a3622; 
        }
        
        .config-invalid { 
            background: #f8d7da; 
            color: #58151c; 
        }
        
        /* Responsive Design */
        @media (max-width: 768px) {
            .container {
                padding: 15px;
            }
            
            .tabs {
                padding: 6px;
                gap: 1px;
            }
            
            .tab {
                padding: 10px 14px;
                font-size: 0.9rem;
                gap: 6px;
            }
            
            .tab i {
                font-size: 0.9rem;
            }
            
            .table-container {
                padding: 15px;
            }
            
            .controls {
                flex-direction: column;
                align-items: stretch;
            }
            
            .search-box,
            .filter-select {
                min-width: auto;
                width: 100%;
            }
            
            .stats {
                grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
                gap: 15px;
            }
            
            .stat-card {
                padding: 20px 15px;
            }
            
            .modal-content {
                width: 95%;
                margin: 20px auto;
                padding: 20px;
            }
        }
        
        /* Bootstrap Icons */
        .bi {
            vertical-align: -0.125em;
        }
        
        .text-success {
            color: #198754 !important;
        }
        
        .text-danger {
            color: #dc3545 !important;
        }
        
        .text-warning {
            color: #ffc107 !important;
        }
        
        /* Icon spacing in content */
        h3 .bi, strong .bi, td .bi {
            margin-right: 6px;
        }
        
        /* Smooth transitions */
        * {
            transition: box-shadow 0.15s ease-out;
        }
    </style>
</head>
<body>
    <div class="header">
        <h1>OpenRecall Database Viewer</h1>
        <p>Property-based unified documentation and activity tracking</p>
    </div>
    
    <div class="container">
        <!-- Tabs -->
        <div class="tabs">
            <button class="tab active" onclick="switchTab('activities')"><i class="bi bi-activity"></i> Activities</button>
            <button class="tab" onclick="switchTab('properties')"><i class="bi bi-list-ul"></i> Properties</button>
            <button class="tab" onclick="switchTab('tags')"><i class="bi bi-tags"></i> Tags</button>
            <button class="tab" onclick="switchTab('projects')"><i class="bi bi-folder"></i> Projects</button>
            <button class="tab" onclick="switchTab('stats')"><i class="bi bi-graph-up"></i> Statistics</button>
            <button class="tab" onclick="switchTab('settings')"><i class="bi bi-gear"></i> Settings</button>
        </div>
        
        <!-- Activities Tab -->
        <div id="activities" class="tab-content active">
            <div class="stats" id="activityStats"></div>
            
            <div class="table-container">
                <div class="table-header">
                    <div class="table-title">Recent Activities</div>
                    <div>
                        <select id="timeRange" onchange="loadActivities()">
                            <option value="today">Today</option>
                            <option value="yesterday">Yesterday</option>
                            <option value="week" selected>This Week</option>
                            <option value="month">This Month</option>
                            <option value="all">All Time</option>
                        </select>
                    </div>
                </div>
                
                <div class="controls">
                    <input type="text" class="search-box" id="activitySearch" placeholder="Search activities..." onkeyup="searchActivities(event)">
                    <button class="btn" onclick="refreshActivities()">Refresh</button>
                </div>
                
                <table id="activitiesTable">
                    <thead>
                        <tr>
                            <th>Application</th>
                            <th>Title</th>
                            <th>Count</th>
                            <th>First Seen</th>
                            <th>Last Seen</th>
                            <th>Duration</th>
                        </tr>
                    </thead>
                    <tbody></tbody>
                </table>
                
                <div class="pagination" id="activitiesPagination"></div>
            </div>
        </div>
        
        <!-- Properties Tab -->
        <div id="properties" class="tab-content">
            <div class="table-container">
                <div class="table-header">
                    <div class="table-title">Properties</div>
                    <div>
                        <button class="btn" onclick="showPropertyForm()">Add Property</button>
                        <button class="btn btn-secondary" onclick="rebuildSearchIndex()">Rebuild Index</button>
                    </div>
                </div>
                
                <div class="controls">
                    <input type="text" class="search-box" id="propertySearch" placeholder="Search properties..." onkeyup="searchProperties(event)">
                    <select class="filter-select" id="typeFilter" onchange="loadProperties()">
                        <option value="">All Types</option>
                        <option value="text">Text</option>
                        <option value="json">JSON</option>
                        <option value="file">File</option>
                        <option value="code_item">Code</option>
                        <option value="documentation">Documentation</option>
                        <option value="section">Section</option>
                    </select>
                    <select class="filter-select" id="tagFilter" onchange="loadProperties()">
                        <option value="">All Tags</option>
                    </select>
                    <button class="btn" onclick="loadProperties()">Filter</button>
                </div>
                
                <table id="propertiesTable">
                    <thead>
                        <tr>
                            <th>Key</th>
                            <th>Type</th>
                            <th>Value Preview</th>
                            <th>Path</th>
                            <th>Tags</th>
                            <th>Updated</th>
                            <th>Actions</th>
                        </tr>
                    </thead>
                    <tbody></tbody>
                </table>
                
                <div class="pagination" id="propertiesPagination"></div>
            </div>
        </div>
        
        <!-- Tags Tab -->
        <div id="tags" class="tab-content">
            <div class="table-container">
                <div class="table-header">
                    <div class="table-title">Tag Hierarchy</div>
                    <button class="btn" onclick="showTagForm()">Add Tag</button>
                </div>
                
                <div class="controls">
                    <select class="filter-select" id="projectFilter" onchange="loadTags()">
                        <option value="default">Default Project</option>
                    </select>
                </div>
                
                <div id="tagTree"></div>
            </div>
        </div>
        
        <!-- Projects Tab -->
        <div id="projects" class="tab-content">
            <div class="table-container">
                <div class="table-header">
                    <div class="table-title">Projects</div>
                    <button class="btn" onclick="showProjectForm()">Add Project</button>
                </div>
                
                <table id="projectsTable">
                    <thead>
                        <tr>
                            <th>Name</th>
                            <th>Slug</th>
                            <th>Status</th>
                            <th>Properties</th>
                            <th>Tags</th>
                            <th>Created</th>
                            <th>Actions</th>
                        </tr>
                    </thead>
                    <tbody></tbody>
                </table>
            </div>
        </div>
        
        
        <!-- Statistics Tab -->
        <div id="stats" class="tab-content">
            <div class="stats" id="databaseStats"></div>
            
            <div class="table-container">
                <div class="table-header">
                    <div class="table-title">Property Type Distribution</div>
                </div>
                <div id="typeChart"></div>
            </div>
        </div>
        
        <!-- Settings Tab -->
        <div id="settings" class="tab-content">
            <div class="table-container">
                <div class="table-header">
                    <div class="table-title">Configuration Settings</div>
                    <div>
                        <button class="btn btn-secondary" onclick="resetToDefaults()">Reset to Defaults</button>
                        <button class="btn btn-success" onclick="saveSettings()">Save Settings</button>
                    </div>
                </div>
                
                <div id="settingsAlert"></div>
                
                <form id="settingsForm" class="settings-form">
                    <div class="form-group">
                        <label class="form-label" for="recallDbPath">OpenRecall Database Path</label>
                        <input type="text" id="recallDbPath" class="form-input" placeholder="/path/to/openrecall.db">
                        <div class="form-description">Path to the OpenRecall activity tracking database</div>
                        <div id="recallDbStatus" class="config-status"></div>
                    </div>
                    
                    <div class="form-group">
                        <label class="form-label" for="docsDbPath">Documentation Database Path</label>
                        <input type="text" id="docsDbPath" class="form-input" placeholder="/path/to/documentation.db">
                        <div class="form-description">Path to the documentation/properties database</div>
                        <div id="docsDbStatus" class="config-status"></div>
                    </div>
                    
                    <div class="form-group">
                        <label class="form-label" for="serverHost">Server Host</label>
                        <input type="text" id="serverHost" class="form-input" placeholder="127.0.0.1">
                        <div class="form-description">Host address for the web interface</div>
                    </div>
                    
                    <div class="form-group">
                        <label class="form-label" for="serverPort">Server Port</label>
                        <input type="number" id="serverPort" class="form-input" placeholder="8084" min="1024" max="65535">
                        <div class="form-description">Port number for the web interface</div>
                    </div>
                    
                    <div class="form-group">
                        <label class="form-label" for="autoRefresh">Auto Refresh Interval (seconds)</label>
                        <input type="number" id="autoRefresh" class="form-input" placeholder="30" min="0" max="3600">
                        <div class="form-description">Automatic refresh interval for data (0 to disable)</div>
                    </div>
                    
                    <div class="form-group">
                        <label class="form-label" for="pageSize">Default Page Size</label>
                        <input type="number" id="pageSize" class="form-input" placeholder="20" min="10" max="100">
                        <div class="form-description">Number of items to show per page</div>
                    </div>
                </form>
                
                <div class="table-container" style="margin-top: 30px;">
                    <div class="table-header">
                        <div class="table-title">Configuration File Status</div>
                        <button class="btn btn-secondary" onclick="loadSettings(true)">Reload Config</button>
                    </div>
                    
                    <table id="configStatusTable">
                        <thead>
                            <tr>
                                <th>Setting</th>
                                <th>Current Value</th>
                                <th>Status</th>
                                <th>Last Updated</th>
                            </tr>
                        </thead>
                        <tbody></tbody>
                    </table>
                </div>
            </div>
        </div>
    </div>
    
    <!-- Modal -->
    <div id="modal" class="modal">
        <div class="modal-content">
            <div class="modal-header">
                <div class="modal-title" id="modalTitle">Details</div>
                <span class="close" onclick="closeModal()">&times;</span>
            </div>
            <div id="modalBody"></div>
        </div>
    </div>
    
    <script>
        let currentTab = 'activities';
        let currentPage = 1;
        const pageSize = 20;
        
        // Initialize
        window.onload = function() {
            loadActivities();
            loadDatabaseStats();
            loadTagOptions();
            loadProjectOptions();
        };
        
        function switchTab(tab) {
            currentTab = tab;
            document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
            document.querySelectorAll('.tab-content').forEach(c => c.classList.remove('active'));
            
            event.target.classList.add('active');
            document.getElementById(tab).classList.add('active');
            
            // Load data for the tab
            currentPage = 1;
            if (tab === 'activities') loadActivities();
            else if (tab === 'properties') loadProperties();
            else if (tab === 'tags') loadTags();
            else if (tab === 'projects') loadProjects();
            else if (tab === 'stats') loadDatabaseStats();
            else if (tab === 'settings') loadSettings();
        }
        
        // Activities functions
        function loadActivities() {
            const timeRange = document.getElementById('timeRange').value;
            
            fetch(`/api/activities?time_range=${timeRange}&page=${currentPage}&size=${pageSize}`)
                .then(r => r.json())
                .then(data => {
                    const tbody = document.querySelector('#activitiesTable tbody');
                    tbody.innerHTML = '';
                    
                    data.activities.forEach(a => {
                        tbody.innerHTML += `
                            <tr>
                                <td>${a.app}</td>
                                <td class="truncate" title="${a.title}">${a.title}</td>
                                <td>${a.count}</td>
                                <td>${formatDate(a.first_seen)}</td>
                                <td>${formatDate(a.last_seen)}</td>
                                <td>${a.duration_minutes} min</td>
                            </tr>
                        `;
                    });
                    
                    updatePagination('activitiesPagination', data.total_pages);
                })
                .catch(err => console.error('Error loading activities:', err));
        }
        
        function searchActivities(event) {
            if (event.key === 'Enter') {
                const query = event.target.value;
                fetch(`/api/search-activities?q=${encodeURIComponent(query)}`)
                    .then(r => r.json())
                    .then(data => {
                        const tbody = document.querySelector('#activitiesTable tbody');
                        tbody.innerHTML = '';
                        
                        data.results.forEach(a => {
                            tbody.innerHTML += `
                                <tr>
                                    <td>${a.app}</td>
                                    <td class="truncate">${a.title}</td>
                                    <td>${a.count}</td>
                                    <td>${formatDate(a.first_seen)}</td>
                                    <td>${formatDate(a.last_seen)}</td>
                                    <td>-</td>
                                </tr>
                            `;
                        });
                    })
                    .catch(err => console.error('Error searching activities:', err));
            }
        }
        
        // Properties functions
        function loadProperties() {
            const typeFilter = document.getElementById('typeFilter').value;
            const tagFilter = document.getElementById('tagFilter').value;
            
            let url = `/api/properties?page=${currentPage}&size=${pageSize}`;
            if (typeFilter) url += `&type=${typeFilter}`;
            if (tagFilter) url += `&tag=${tagFilter}`;
            
            fetch(url)
                .then(r => r.json())
                .then(data => {
                    const tbody = document.querySelector('#propertiesTable tbody');
                    tbody.innerHTML = '';
                    
                    if (data.error) {
                        tbody.innerHTML = `
                            <tr>
                                <td colspan="7" style="text-align: center; padding: 20px; color: #666;">
                                    <strong><i class="bi bi-exclamation-triangle"></i> ${data.error}</strong><br>
                                    <small>The documentation database needs to be initialized with the new schema.</small>
                                </td>
                            </tr>
                        `;
                        updatePagination('propertiesPagination', 0);
                        return;
                    }
                    
                    if (!data.properties || data.properties.length === 0) {
                        tbody.innerHTML = `
                            <tr>
                                <td colspan="7" style="text-align: center; padding: 20px; color: #666;">
                                    <i class="bi bi-file-text"></i> No properties found.<br>
                                    <small>Use the DocumentationMCP server to add properties to the database.</small>
                                </td>
                            </tr>
                        `;
                        updatePagination('propertiesPagination', 0);
                        return;
                    }
                    
                    data.properties.forEach(p => {
                        const tags = p.tags.filter(tag => tag && tag.trim()).map(tag => `<span class="tag">${tag}</span>`).join('');
                        const typeClass = `type-${p.type.replace('_', '-')}`;
                        
                        tbody.innerHTML += `
                            <tr>
                                <td><strong>${p.key}</strong></td>
                                <td><span class="type-badge ${typeClass}">${p.type}</span></td>
                                <td class="truncate" title="${p.value || ''}">${p.value || '<empty>'}</td>
                                <td class="property-path">${p.path || ''}</td>
                                <td>${tags}</td>
                                <td>${formatDate(p.updated_at)}</td>
                                <td>
                                    <button onclick="viewProperty('${p.id}')">View</button>
                                    <button onclick="viewPropertyTree('${p.key}')">Tree</button>
                                </td>
                            </tr>
                        `;
                    });
                    
                    updatePagination('propertiesPagination', data.total_pages || 0);
                })
                .catch(err => {
                    console.error('Error loading properties:', err);
                    const tbody = document.querySelector('#propertiesTable tbody');
                    tbody.innerHTML = `
                        <tr>
                            <td colspan="7" style="text-align: center; padding: 20px; color: #dc3545;">
                                <i class="bi bi-x-circle"></i> Error loading properties: ${err.message}
                            </td>
                        </tr>
                    `;
                });
        }
        
        function searchProperties(event) {
            if (event.key === 'Enter') {
                const query = event.target.value;
                if (!query.trim()) {
                    loadProperties();
                    return;
                }
                
                fetch(`/api/search-properties?q=${encodeURIComponent(query)}`)
                    .then(r => r.json())
                    .then(data => {
                        const tbody = document.querySelector('#propertiesTable tbody');
                        tbody.innerHTML = '';
                        
                        data.properties.forEach(p => {
                            const tags = p.tags.map(tag => `<span class="tag">${tag}</span>`).join('');
                            const typeClass = `type-${p.type.replace('_', '-')}`;
                            
                            tbody.innerHTML += `
                                <tr>
                                    <td><strong>${p.key}</strong></td>
                                    <td><span class="type-badge ${typeClass}">${p.type}</span></td>
                                    <td class="truncate">${p.value || '<empty>'}</td>
                                    <td class="property-path">${p.path || ''}</td>
                                    <td>${tags}</td>
                                    <td>-</td>
                                    <td>
                                        <button onclick="viewProperty('${p.id}')">View</button>
                                    </td>
                                </tr>
                            `;
                        });
                    })
                    .catch(err => console.error('Error searching properties:', err));
            }
        }
        
        function viewProperty(id) {
            fetch(`/api/properties/${id}`)
                .then(r => r.json())
                .then(data => {
                    document.getElementById('modalTitle').textContent = data.key;
                    document.getElementById('modalBody').innerHTML = `
                        <p><strong>ID:</strong> ${data.id}</p>
                        <p><strong>Type:</strong> <span class="type-badge type-${data.type.replace('_', '-')}">${data.type}</span></p>
                        <p><strong>Path:</strong> ${data.path || 'Root'}</p>
                        <p><strong>Tags:</strong> ${data.tags.map(t => `<span class="tag">${t}</span>`).join('')}</p>
                        <p><strong>Created:</strong> ${formatDate(data.created_at)}</p>
                        <p><strong>Updated:</strong> ${formatDate(data.updated_at)}</p>
                        <p><strong>Value:</strong></p>
                        <div class="code-block">${data.value || '<empty>'}</div>
                    `;
                    document.getElementById('modal').style.display = 'block';
                })
                .catch(err => console.error('Error loading property:', err));
        }
        
        function viewPropertyTree(key) {
            fetch(`/api/property-tree/${encodeURIComponent(key)}`)
                .then(r => r.json())
                .then(data => {
                    document.getElementById('modalTitle').textContent = `Tree: ${key}`;
                    document.getElementById('modalBody').innerHTML = renderPropertyTree(data.tree);
                    document.getElementById('modal').style.display = 'block';
                })
                .catch(err => console.error('Error loading property tree:', err));
        }
        
        function renderPropertyTree(node, level = 0) {
            const indent = '  '.repeat(level);
            const typeClass = `type-${node.type.replace('_', '-')}`;
            let html = `
                <div class="tree-item" style="margin-left: ${level * 20}px">
                    <strong>${node.key}</strong> 
                    <span class="type-badge ${typeClass}">${node.type}</span><br>
                    <div class="code-block" style="margin: 5px 0; font-size: 12px;">${node.value || '<empty>'}</div>
                </div>
            `;
            
            if (node.children && node.children.length > 0) {
                node.children.forEach(child => {
                    html += renderPropertyTree(child, level + 1);
                });
            }
            
            return html;
        }
        
        // Tags functions
        function loadTags() {
            const project = document.getElementById('projectFilter').value;
            
            fetch(`/api/tag-tree?project=${project}`)
                .then(r => r.json())
                .then(data => {
                    const tagTree = document.getElementById('tagTree');
                    
                    if (data.error) {
                        tagTree.innerHTML = `
                            <div style="text-align: center; padding: 40px; color: #666;">
                                <h3><i class="bi bi-exclamation-triangle"></i> ${data.error}</h3>
                                <p>The documentation database needs to be initialized with the new schema.<br>
                                Use the DocumentationMCP server to create tags and properties.</p>
                            </div>
                        `;
                        return;
                    }
                    
                    if (!data.tags || data.tags.length === 0) {
                        tagTree.innerHTML = `
                            <div style="text-align: center; padding: 40px; color: #666;">
                                <h3><i class="bi bi-tags"></i> No tags found</h3>
                                <p>Use the DocumentationMCP server to create hierarchical tags.</p>
                            </div>
                        `;
                        return;
                    }
                    
                    tagTree.innerHTML = renderTagTree(data.tags);
                })
                .catch(err => {
                    console.error('Error loading tags:', err);
                    document.getElementById('tagTree').innerHTML = `
                        <div style="text-align: center; padding: 40px; color: #dc3545;">
                            <h3><i class="bi bi-x-circle"></i> Error loading tags</h3>
                            <p>${err.message}</p>
                        </div>
                    `;
                });
        }
        
        function renderTagTree(tags, level = 0) {
            let html = '';
            tags.forEach(tag => {
                html += `
                    <div class="tree-item" style="margin-left: ${level * 20}px">
                        <span class="tree-toggle" onclick="toggleTag('${tag.id}')"><i class="bi bi-folder"></i></span>
                        <span class="tag" style="background-color: ${tag.color || '#e0e0e0'}">${tag.name}</span>
                        <span class="property-path">(${tag.property_count} properties)</span>
                        <div id="tag-${tag.id}" class="tree-children">
                            ${renderTagTree(tag.children, level + 1)}
                        </div>
                    </div>
                `;
            });
            return html;
        }
        
        // Projects functions
        function loadProjects() {
            fetch('/api/projects')
                .then(r => r.json())
                .then(data => {
                    const tbody = document.querySelector('#projectsTable tbody');
                    tbody.innerHTML = '';
                    
                    data.projects.forEach(p => {
                        tbody.innerHTML += `
                            <tr>
                                <td><strong>${p.name}</strong></td>
                                <td>${p.slug}</td>
                                <td>${p.is_active ? '<i class="bi bi-check-circle text-success"></i> Active' : '<i class="bi bi-x-circle text-danger"></i> Inactive'}</td>
                                <td>${p.property_count}</td>
                                <td>${p.tag_count}</td>
                                <td>${formatDate(p.created_at)}</td>
                                <td>
                                    <button onclick="viewProject('${p.id}')">View</button>
                                </td>
                            </tr>
                        `;
                    });
                })
                .catch(err => console.error('Error loading projects:', err));
        }
        
        
        // Statistics functions
        function loadDatabaseStats() {
            fetch('/api/database-stats')
                .then(r => r.json())
                .then(data => {
                    // Activity stats
                    document.getElementById('activityStats').innerHTML = `
                        <div class="stat-card">
                            <div class="stat-number">${data.total_entries || 0}</div>
                            <div class="stat-label">Total Entries</div>
                        </div>
                        <div class="stat-card">
                            <div class="stat-number">${data.unique_apps || 0}</div>
                            <div class="stat-label">Unique Apps</div>
                        </div>
                        <div class="stat-card">
                            <div class="stat-number">${data.days_of_data || 0}</div>
                            <div class="stat-label">Days of Data</div>
                        </div>
                    `;
                    
                    // Database stats
                    document.getElementById('databaseStats').innerHTML = `
                        <div class="stat-card">
                            <div class="stat-number">${data.total_properties || 0}</div>
                            <div class="stat-label">Total Properties</div>
                        </div>
                        <div class="stat-card">
                            <div class="stat-number">${data.total_tags || 0}</div>
                            <div class="stat-label">Tags</div>
                        </div>
                        <div class="stat-card">
                            <div class="stat-number">${data.active_projects || 0}</div>
                            <div class="stat-label">Active Projects</div>
                        </div>
                        <div class="stat-card">
                            <div class="stat-number">${data.total_versions || 0}</div>
                            <div class="stat-label">Versions</div>
                        </div>
                        <div class="stat-card">
                            <div class="stat-number">${data.index_coverage || 0}%</div>
                            <div class="stat-label">Search Index Coverage</div>
                        </div>
                        <div class="stat-card">
                            <div class="stat-number">${data.size_mb || 0}</div>
                            <div class="stat-label">Database Size (MB)</div>
                        </div>
                    `;
                    
                    // Property type chart
                    if (data.properties_by_type) {
                        let chartHtml = '<div style="display: flex; flex-wrap: wrap; gap: 10px;">';
                        Object.entries(data.properties_by_type).forEach(([type, count]) => {
                            const typeClass = `type-${type.replace('_', '-')}`;
                            chartHtml += `
                                <div class="stat-card" style="min-width: 150px;">
                                    <div class="stat-number">${count}</div>
                                    <div class="stat-label">
                                        <span class="type-badge ${typeClass}">${type}</span>
                                    </div>
                                </div>
                            `;
                        });
                        chartHtml += '</div>';
                        document.getElementById('typeChart').innerHTML = chartHtml;
                    }
                })
                .catch(err => console.error('Error loading database stats:', err));
        }
        
        // Utility functions
        function loadTagOptions() {
            fetch('/api/tags')
                .then(r => r.json())
                .then(data => {
                    const select = document.getElementById('tagFilter');
                    select.innerHTML = '<option value="">All Tags</option>';
                    
                    if (data.error) {
                        select.innerHTML += '<option value="" disabled><i class="bi bi-exclamation-triangle"></i> ' + data.error + '</option>';
                        return;
                    }
                    
                    if (data.tags && data.tags.length > 0) {
                        data.tags.forEach(tag => {
                            select.innerHTML += `<option value="${tag.slug}">${tag.name}</option>`;
                        });
                    } else {
                        select.innerHTML += '<option value="" disabled>No tags available</option>';
                    }
                })
                .catch(err => {
                    console.error('Error loading tag options:', err);
                    const select = document.getElementById('tagFilter');
                    select.innerHTML = '<option value="">All Tags</option><option value="" disabled><i class="bi bi-x-circle"></i> Error loading tags</option>';
                });
        }
        
        function loadProjectOptions() {
            fetch('/api/projects')
                .then(r => r.json())
                .then(data => {
                    const select = document.getElementById('projectFilter');
                    select.innerHTML = '';
                    data.projects.forEach(project => {
                        select.innerHTML += `<option value="${project.slug}">${project.name}</option>`;
                    });
                })
                .catch(err => console.error('Error loading project options:', err));
        }
        
        function updatePagination(elementId, totalPages) {
            const pagination = document.getElementById(elementId);
            pagination.innerHTML = '';
            
            for (let i = 1; i <= Math.min(totalPages, 10); i++) {
                pagination.innerHTML += `
                    <button class="page-btn ${i === currentPage ? 'active' : ''}" 
                            onclick="changePage(${i})">${i}</button>
                `;
            }
        }
        
        function changePage(page) {
            currentPage = page;
            if (currentTab === 'activities') loadActivities();
            else if (currentTab === 'properties') loadProperties();
        }
        
        function formatDate(dateStr) {
            if (!dateStr) return '-';
            const date = new Date(dateStr);
            return date.toLocaleDateString() + ' ' + date.toLocaleTimeString();
        }
        
        function closeModal() {
            document.getElementById('modal').style.display = 'none';
        }
        
        function refreshActivities() {
            loadActivities();
            loadDatabaseStats();
        }
        
        function rebuildSearchIndex() {
            if (confirm('Rebuild search index? This may take a moment.')) {
                fetch('/api/rebuild-search-index', { method: 'POST' })
                    .then(r => r.json())
                    .then(data => {
                        alert(data.message || 'Search index rebuilt');
                        loadDatabaseStats();
                    })
                    .catch(err => {
                        console.error('Error rebuilding index:', err);
                        alert('Error rebuilding search index');
                    });
            }
        }
        
        // Form functions (placeholders)
        function showPropertyForm() {
            alert('Property form not implemented yet');
        }
        
        function showTagForm() {
            alert('Tag form not implemented yet');
        }
        
        function showProjectForm() {
            alert('Project form not implemented yet');
        }
        
        
        // Settings functions
        function loadSettings(force = false) {
            fetch('/api/config' + (force ? '?reload=true' : ''))
                .then(r => r.json())
                .then(data => {
                    if (data.error) {
                        showAlert('Error loading settings: ' + data.error, 'error');
                        return;
                    }
                    
                    // Populate form fields
                    document.getElementById('recallDbPath').value = data.recall_db_path || '';
                    document.getElementById('docsDbPath').value = data.docs_db_path || '';
                    document.getElementById('serverHost').value = data.server.host || '127.0.0.1';
                    document.getElementById('serverPort').value = data.server.port || 8084;
                    document.getElementById('autoRefresh').value = data.interface.auto_refresh_seconds || 30;
                    document.getElementById('pageSize').value = data.interface.default_page_size || 20;
                    
                    // Update status indicators
                    updateDatabaseStatus('recallDbStatus', data.recall_db_status);
                    updateDatabaseStatus('docsDbStatus', data.docs_db_status);
                    
                    // Update config status table
                    updateConfigStatusTable(data);
                })
                .catch(err => {
                    console.error('Error loading settings:', err);
                    showAlert('Failed to load settings', 'error');
                });
        }
        
        function saveSettings() {
            const settings = {
                recall_db_path: document.getElementById('recallDbPath').value,
                docs_db_path: document.getElementById('docsDbPath').value,
                server: {
                    host: document.getElementById('serverHost').value,
                    port: parseInt(document.getElementById('serverPort').value)
                },
                interface: {
                    auto_refresh_seconds: parseInt(document.getElementById('autoRefresh').value),
                    default_page_size: parseInt(document.getElementById('pageSize').value)
                }
            };
            
            fetch('/api/config', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify(settings)
            })
            .then(r => r.json())
            .then(data => {
                if (data.error) {
                    showAlert('Error saving settings: ' + data.error, 'error');
                } else {
                    showAlert('Settings saved successfully! Restart required for server settings to take effect.', 'success');
                    loadSettings(true); // Reload to show updated status
                }
            })
            .catch(err => {
                console.error('Error saving settings:', err);
                showAlert('Failed to save settings', 'error');
            });
        }
        
        function resetToDefaults() {
            if (confirm('Reset all settings to defaults? This cannot be undone.')) {
                fetch('/api/config/reset', { method: 'POST' })
                    .then(r => r.json())
                    .then(data => {
                        if (data.error) {
                            showAlert('Error resetting settings: ' + data.error, 'error');
                        } else {
                            showAlert('Settings reset to defaults', 'success');
                            loadSettings(true);
                        }
                    })
                    .catch(err => {
                        console.error('Error resetting settings:', err);
                        showAlert('Failed to reset settings', 'error');
                    });
            }
        }
        
        function updateDatabaseStatus(elementId, status) {
            const element = document.getElementById(elementId);
            if (!element) return;
            
            if (status && status.exists) {
                element.className = 'config-status config-valid';
                element.textContent = `✓ Valid (${status.size_mb} MB, ${status.entries || 'N/A'} entries)`;
            } else {
                element.className = 'config-status config-invalid';
                element.textContent = status ? status.error || '✗ File not found' : '✗ Not configured';
            }
        }
        
        function updateConfigStatusTable(config) {
            const tbody = document.querySelector('#configStatusTable tbody');
            tbody.innerHTML = '';
            
            const settings = [
                { key: 'Recall DB', value: config.recall_db_path, status: config.recall_db_status },
                { key: 'Docs DB', value: config.docs_db_path, status: config.docs_db_status },
                { key: 'Server Host', value: config.server.host, status: { exists: true } },
                { key: 'Server Port', value: config.server.port, status: { exists: true } },
                { key: 'Auto Refresh', value: config.interface.auto_refresh_seconds + 's', status: { exists: true } },
                { key: 'Page Size', value: config.interface.default_page_size, status: { exists: true } }
            ];
            
            settings.forEach(setting => {
                const statusClass = setting.status && setting.status.exists ? 'config-valid' : 'config-invalid';
                const statusText = setting.status && setting.status.exists ? 'Valid' : (setting.status ? setting.status.error || 'Invalid' : 'Not Set');
                
                tbody.innerHTML += `
                    <tr>
                        <td><strong>${setting.key}</strong></td>
                        <td class="truncate" title="${setting.value || ''}">${setting.value || '<not set>'}</td>
                        <td><span class="config-status ${statusClass}">${statusText}</span></td>
                        <td>${config.last_updated || '-'}</td>
                    </tr>
                `;
            });
        }
        
        function showAlert(message, type) {
            const alertDiv = document.getElementById('settingsAlert');
            alertDiv.innerHTML = `<div class="alert alert-${type === 'success' ? 'success' : 'error'}">${message}</div>`;
            setTimeout(() => {
                alertDiv.innerHTML = '';
            }, 5000);
        }
    </script>
</body>
</html>
"""


class DatabaseViewer:
    def __init__(self, config_path="database_viewer.ini", recall_db_path=None, docs_db_path=None):
        self.config_path = config_path
        self.config = self.load_config()
        
        # Override with command line arguments if provided
        if recall_db_path:
            self.config.set('database', 'recall_db_path', recall_db_path)
        if docs_db_path:
            self.config.set('database', 'docs_db_path', docs_db_path)
            
        self.recall_db_path = self.config.get('database', 'recall_db_path', fallback=None)
        self.docs_db_path = self.config.get('database', 'docs_db_path', fallback='documentation.db')
        
        self.app = Flask(__name__)
        self.init_documentation_db()
        self.setup_routes()
    
    def load_config(self):
        """Load configuration from INI file, create default if doesn't exist"""
        config = configparser.ConfigParser()
        
        # Set default configuration
        config['database'] = {
            'recall_db_path': '',
            'docs_db_path': 'documentation.db'
        }
        config['server'] = {
            'host': '127.0.0.1',
            'port': '8084'
        }
        config['interface'] = {
            'auto_refresh_seconds': '30',
            'default_page_size': '20'
        }
        
        # Load from file if exists
        if Path(self.config_path).exists():
            try:
                config.read(self.config_path)
            except Exception as e:
                print(f"Warning: Error reading config file {self.config_path}: {e}")
                print("Using default configuration")
        else:
            # Create default config file
            self.save_config(config)
            
        return config
    
    def save_config(self, config=None):
        """Save configuration to INI file"""
        if config is None:
            config = self.config
            
        try:
            # Add metadata
            config['metadata'] = {
                'last_updated': datetime.now().isoformat(),
                'version': '2.0.0'
            }
            
            with open(self.config_path, 'w') as f:
                config.write(f)
            return True
        except Exception as e:
            print(f"Error saving config: {e}")
            return False
    
    def get_database_status(self, db_path):
        """Get status information about a database file"""
        if not db_path:
            return {'exists': False, 'error': 'Path not configured'}
            
        path = Path(db_path)
        if not path.exists():
            return {'exists': False, 'error': 'File does not exist'}
            
        try:
            size_mb = round(path.stat().st_size / 1024 / 1024, 2)
            
            # Try to get entry count for validation
            with sqlite3.connect(db_path) as conn:
                cursor = conn.cursor()
                
                # Check if it's an OpenRecall DB or Documentation DB
                cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
                tables = [row[0] for row in cursor.fetchall()]
                
                if 'entries' in tables:  # OpenRecall DB
                    cursor.execute("SELECT COUNT(*) FROM entries")
                    entries = cursor.fetchone()[0]
                elif 'properties' in tables:  # Documentation DB
                    cursor.execute("SELECT COUNT(*) FROM properties WHERE status = 'active'")
                    entries = cursor.fetchone()[0]
                else:
                    entries = 'Unknown'
                    
            return {
                'exists': True,
                'size_mb': size_mb,
                'entries': entries,
                'tables': tables
            }
        except Exception as e:
            return {'exists': False, 'error': f'Database error: {str(e)}'}
    
    def init_documentation_db(self):
        """Initialize documentation database with required tables if they don't exist"""
        if not self.docs_db_path or not Path(self.docs_db_path).parent.exists():
            return
            
        try:
            with sqlite3.connect(self.docs_db_path) as conn:
                cursor = conn.cursor()
                
                # Check if new schema tables exist
                cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='properties'")
                if not cursor.fetchone():
                    # Create the new property-based schema
                    self.create_documentation_schema(cursor)
                    conn.commit()
                    print(f"Initialized documentation database schema: {self.docs_db_path}")
                    
        except Exception as e:
            print(f"Warning: Could not initialize documentation database: {e}")
    
    def create_documentation_schema(self, cursor):
        """Create the property-based documentation schema"""
        # Enable foreign keys
        cursor.execute("PRAGMA foreign_keys = ON")
        
        # Create PROJECTS table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS projects (
                id TEXT PRIMARY KEY DEFAULT (lower(hex(randomblob(16)))),
                name TEXT NOT NULL,
                slug TEXT UNIQUE NOT NULL,
                is_active BOOLEAN DEFAULT 1,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_projects_slug ON projects(slug)")
        
        # Create TAGS table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS tags (
                id TEXT PRIMARY KEY DEFAULT (lower(hex(randomblob(16)))),
                name TEXT NOT NULL,
                slug TEXT NOT NULL,
                parent_tag_id TEXT,
                project_id TEXT,
                color TEXT,
                sort_order INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (parent_tag_id) REFERENCES tags(id) ON DELETE CASCADE,
                FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE,
                UNIQUE(slug, parent_tag_id, project_id)
            )
        """)
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_tags_hierarchy ON tags(slug, parent_tag_id, project_id)")
        
        # Create PROPERTIES table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS properties (
                id TEXT PRIMARY KEY DEFAULT (lower(hex(randomblob(16)))),
                key TEXT NOT NULL,
                value TEXT,
                type TEXT DEFAULT 'text',
                parent_id TEXT,
                status TEXT DEFAULT 'active',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (parent_id) REFERENCES properties(id) ON DELETE CASCADE
            )
        """)
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_properties_key_parent ON properties(key, parent_id, status)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_properties_parent ON properties(parent_id)")
        
        # Create PROPERTY_TAGS junction table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS property_tags (
                property_id TEXT NOT NULL,
                tag_id TEXT NOT NULL,
                assigned_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (property_id, tag_id),
                FOREIGN KEY (property_id) REFERENCES properties(id) ON DELETE CASCADE,
                FOREIGN KEY (tag_id) REFERENCES tags(id) ON DELETE CASCADE
            )
        """)
        
        # Create VERSIONS table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS versions (
                id TEXT PRIMARY KEY DEFAULT (lower(hex(randomblob(16)))),
                property_id TEXT NOT NULL,
                version_number INTEGER NOT NULL,
                value_snapshot TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (property_id) REFERENCES properties(id) ON DELETE CASCADE
            )
        """)
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_versions_property ON versions(property_id, version_number)")
        
        # Create SEARCH_INDEX table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS search_index (
                id TEXT PRIMARY KEY DEFAULT (lower(hex(randomblob(16)))),
                property_id TEXT UNIQUE NOT NULL,
                search_vector TEXT,
                computed_path TEXT,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (property_id) REFERENCES properties(id) ON DELETE CASCADE
            )
        """)
        
        # Create default project
        cursor.execute("""
            INSERT OR IGNORE INTO projects (name, slug) 
            VALUES ('Default', 'default')
        """)
        
        # Get default project ID and create sample tags
        cursor.execute("SELECT id FROM projects WHERE slug = 'default'")
        project_row = cursor.fetchone()
        if project_row:
            project_id = project_row[0]
            default_tags = [
                ('Documentation', 'documentation'),
                ('Code', 'code'),
                ('API', 'api'),
                ('Configuration', 'config'),
                ('Notes', 'notes')
            ]
            for name, slug in default_tags:
                cursor.execute("""
                    INSERT OR IGNORE INTO tags (name, slug, project_id) 
                    VALUES (?, ?, ?)
                """, (name, slug, project_id))
        
        # Create sample property to test the system
        cursor.execute("""
            INSERT OR IGNORE INTO properties (key, value, type)
            VALUES ('welcome-message', 'Welcome to the new property-based documentation system!', 'text')
        """)
    
    def setup_routes(self):
        @self.app.route('/')
        def home():
            return render_template_string(HTML_TEMPLATE)
        
        # Activity-related routes (OpenRecall database)
        @self.app.route('/api/activities')
        def get_activities():
            time_range = request.args.get('time_range', 'week')
            page = int(request.args.get('page', 1))
            size = int(request.args.get('size', 20))
            
            try:
                with sqlite3.connect(self.recall_db_path) as conn:
                    cursor = conn.cursor()
                    
                    # Get time filter
                    cursor.execute("SELECT MAX(timestamp) FROM entries")
                    max_ts_result = cursor.fetchone()
                    if not max_ts_result or not max_ts_result[0]:
                        return jsonify({'activities': [], 'total': 0, 'page': page, 'total_pages': 0})
                    
                    max_ts = max_ts_result[0]
                    
                    if time_range == 'today':
                        start_ts = int(datetime.fromtimestamp(max_ts).replace(hour=0, minute=0, second=0).timestamp())
                    elif time_range == 'yesterday':
                        yesterday = datetime.fromtimestamp(max_ts).replace(hour=0, minute=0, second=0) - timedelta(days=1)
                        start_ts = int(yesterday.timestamp())
                    elif time_range == 'week':
                        start_ts = max_ts - (7 * 86400)
                    elif time_range == 'month':
                        start_ts = max_ts - (30 * 86400)
                    else:
                        cursor.execute("SELECT MIN(timestamp) FROM entries")
                        min_ts_result = cursor.fetchone()
                        start_ts = min_ts_result[0] if min_ts_result and min_ts_result[0] else max_ts
                    
                    # Get activities with pagination
                    offset = (page - 1) * size
                    cursor.execute("""
                        SELECT app, title, COUNT(*) as count,
                               MIN(timestamp) as first_seen,
                               MAX(timestamp) as last_seen
                        FROM entries
                        WHERE timestamp >= ?
                        GROUP BY app, title
                        ORDER BY count DESC
                        LIMIT ? OFFSET ?
                    """, (start_ts, size, offset))
                    
                    activities = []
                    for row in cursor.fetchall():
                        app, title, count, first_ts, last_ts = row
                        activities.append({
                            'app': app,
                            'title': title,
                            'count': count,
                            'first_seen': datetime.fromtimestamp(first_ts).isoformat(),
                            'last_seen': datetime.fromtimestamp(last_ts).isoformat(),
                            'duration_minutes': round((last_ts - first_ts) / 60, 1)
                        })
                    
                    # Get total count for pagination
                    cursor.execute("""
                        SELECT COUNT(DISTINCT app || title)
                        FROM entries
                        WHERE timestamp >= ?
                    """, (start_ts,))
                    total = cursor.fetchone()[0]
                    
                    return jsonify({
                        'activities': activities,
                        'total': total,
                        'page': page,
                        'total_pages': (total + size - 1) // size
                    })
                    
            except Exception as e:
                return jsonify({'error': str(e)}), 500
        
        @self.app.route('/api/search-activities')
        def search_activities():
            query = request.args.get('q', '')
            
            try:
                with sqlite3.connect(self.recall_db_path) as conn:
                    cursor = conn.cursor()
                    
                    cursor.execute("""
                        SELECT app, title, COUNT(*) as count,
                               MIN(timestamp) as first_seen,
                               MAX(timestamp) as last_seen
                        FROM entries
                        WHERE title LIKE ? OR app LIKE ?
                        GROUP BY app, title
                        ORDER BY count DESC
                        LIMIT 20
                    """, (f'%{query}%', f'%{query}%'))
                    
                    results = []
                    for row in cursor.fetchall():
                        app, title, count, first_ts, last_ts = row
                        results.append({
                            'app': app,
                            'title': title,
                            'count': count,
                            'first_seen': datetime.fromtimestamp(first_ts).isoformat(),
                            'last_seen': datetime.fromtimestamp(last_ts).isoformat()
                        })
                    
                    return jsonify({'results': results})
                    
            except Exception as e:
                return jsonify({'error': str(e)}), 500
        
        # Property-related routes (Documentation database)
        @self.app.route('/api/properties')
        def get_properties():
            try:
                page = int(request.args.get('page', 1))
                size = int(request.args.get('size', 20))
                type_filter = request.args.get('type')
                tag_filter = request.args.get('tag')
                
                if not self.docs_db_path or not Path(self.docs_db_path).exists():
                    return jsonify({
                        'properties': [],
                        'total': 0,
                        'page': page,
                        'total_pages': 0,
                        'error': 'Documentation database not found'
                    })
                
                with sqlite3.connect(self.docs_db_path) as conn:
                    cursor = conn.cursor()
                    
                    # Check if properties table exists
                    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='properties'")
                    if not cursor.fetchone():
                        return jsonify({
                            'properties': [],
                            'total': 0,
                            'page': page,
                            'total_pages': 0,
                            'error': 'Properties table not found. Please run the DocumentationMCP server first to initialize the database.'
                        })
                    
                    # Build query - simple approach without GROUP_CONCAT to avoid SQL errors
                    sql = """
                        SELECT DISTINCT p.id, p.key, p.value, p.type, p.updated_at, si.computed_path
                        FROM properties p
                        LEFT JOIN search_index si ON p.id = si.property_id
                        LEFT JOIN property_tags pt ON p.id = pt.property_id
                        LEFT JOIN tags t ON pt.tag_id = t.id
                        WHERE p.status = 'active'
                    """
                    params = []
                    
                    if type_filter:
                        sql += " AND p.type = ?"
                        params.append(type_filter)
                    
                    if tag_filter:
                        sql += " AND t.slug = ?"
                        params.append(tag_filter)
                    
                    sql += " ORDER BY p.updated_at DESC"
                    
                    # Get total count
                    count_sql = """
                        SELECT COUNT(DISTINCT p.id)
                        FROM properties p
                        LEFT JOIN property_tags pt ON p.id = pt.property_id
                        LEFT JOIN tags t ON pt.tag_id = t.id
                        WHERE p.status = 'active'
                    """
                    count_params = []
                    if type_filter:
                        count_sql += " AND p.type = ?"
                        count_params.append(type_filter)
                    if tag_filter:
                        count_sql += " AND t.slug = ?"
                        count_params.append(tag_filter)
                    
                    cursor.execute(count_sql, count_params)
                    total = cursor.fetchone()[0]
                    
                    # Apply pagination
                    offset = (page - 1) * size
                    sql += f" LIMIT ? OFFSET ?"
                    params.extend([size, offset])
                    
                    cursor.execute(sql, params)
                    
                    properties = []
                    for row in cursor.fetchall():
                        prop_id, key, value, prop_type, updated_at, path = row
                        
                        # Get tags separately to avoid GROUP_CONCAT issues
                        cursor.execute("""
                            SELECT t.name FROM tags t
                            JOIN property_tags pt ON t.id = pt.tag_id
                            WHERE pt.property_id = ?
                        """, (prop_id,))
                        tag_rows = cursor.fetchall()
                        tags = [str(tag_row[0]) for tag_row in tag_rows] if tag_rows else []
                        
                        properties.append({
                            'id': prop_id,
                            'key': key,
                            'value': value[:200] if value else None,
                            'type': prop_type,
                            'path': path,
                            'tags': tags,
                            'updated_at': updated_at
                        })
                    
                    return jsonify({
                        'properties': properties,
                        'total': total,
                        'page': page,
                        'total_pages': (total + size - 1) // size
                    })
                    
            except Exception as e:
                return jsonify({'error': str(e)}), 500
        
        @self.app.route('/api/properties/<property_id>')
        def get_property(property_id):
            try:
                with sqlite3.connect(self.docs_db_path) as conn:
                    cursor = conn.cursor()
                    
                    cursor.execute("""
                        SELECT p.id, p.key, p.value, p.type, p.created_at, p.updated_at, si.computed_path
                        FROM properties p
                        LEFT JOIN search_index si ON p.id = si.property_id
                        WHERE p.id = ? AND p.status = 'active'
                    """, (property_id,))
                    
                    row = cursor.fetchone()
                    if not row:
                        return jsonify({'error': 'Property not found'}), 404
                    
                    prop_id, key, value, prop_type, created_at, updated_at, path = row
                    
                    # Get tags separately
                    cursor.execute("""
                        SELECT t.name FROM tags t
                        JOIN property_tags pt ON t.id = pt.tag_id
                        WHERE pt.property_id = ?
                    """, (prop_id,))
                    tag_rows = cursor.fetchall()
                    tags = [str(tag_row[0]) for tag_row in tag_rows] if tag_rows else []
                    
                    return jsonify({
                        'id': prop_id,
                        'key': key,
                        'value': value,
                        'type': prop_type,
                        'path': path,
                        'tags': tags,
                        'created_at': created_at,
                        'updated_at': updated_at
                    })
                    
            except Exception as e:
                return jsonify({'error': str(e)}), 500
        
        @self.app.route('/api/search-properties')
        def search_properties():
            query = request.args.get('q', '')
            
            try:
                with sqlite3.connect(self.docs_db_path) as conn:
                    cursor = conn.cursor()
                    
                    cursor.execute("""
                        SELECT DISTINCT p.id, p.key, p.value, p.type, si.computed_path
                        FROM properties p
                        LEFT JOIN search_index si ON p.id = si.property_id
                        WHERE p.status = 'active'
                        AND (p.key LIKE ? OR p.value LIKE ? OR si.search_vector LIKE ?)
                        ORDER BY p.updated_at DESC
                        LIMIT 50
                    """, (f'%{query}%', f'%{query}%', f'%{query}%'))
                    
                    properties = []
                    for row in cursor.fetchall():
                        prop_id, key, value, prop_type, path = row
                        
                        # Get tags separately
                        cursor.execute("""
                            SELECT t.name FROM tags t
                            JOIN property_tags pt ON t.id = pt.tag_id
                            WHERE pt.property_id = ?
                        """, (prop_id,))
                        tag_rows = cursor.fetchall()
                        tags = [str(tag_row[0]) for tag_row in tag_rows] if tag_rows else []
                        
                        properties.append({
                            'id': prop_id,
                            'key': key,
                            'value': value[:200] if value else None,
                            'type': prop_type,
                            'path': path,
                            'tags': tags
                        })
                    
                    return jsonify({
                        'query': query,
                        'total_results': len(properties),
                        'properties': properties
                    })
                    
            except Exception as e:
                return jsonify({'error': str(e)}), 500
        
        @self.app.route('/api/property-tree/<key>')
        def get_property_tree(key):
            try:
                with sqlite3.connect(self.docs_db_path) as conn:
                    cursor = conn.cursor()
                    
                    # Get root property
                    cursor.execute("""
                        SELECT id, key, value, type FROM properties 
                        WHERE key = ? AND status = 'active'
                    """, (key,))
                    root = cursor.fetchone()
                    
                    if not root:
                        return jsonify({'error': f'Property {key} not found'}), 404
                    
                    def build_tree(parent_id, depth=0):
                        if depth >= 5:  # Prevent infinite recursion
                            return []
                        
                        cursor.execute("""
                            SELECT id, key, value, type FROM properties 
                            WHERE parent_id = ? AND status = 'active'
                            ORDER BY key
                        """, (parent_id,))
                        
                        children = []
                        for row in cursor.fetchall():
                            child_id, child_key, child_value, child_type = row
                            child = {
                                'id': child_id,
                                'key': child_key,
                                'value': child_value,
                                'type': child_type,
                                'children': build_tree(child_id, depth + 1)
                            }
                            children.append(child)
                        
                        return children
                    
                    root_id, root_key, root_value, root_type = root
                    tree = {
                        'id': root_id,
                        'key': root_key,
                        'value': root_value,
                        'type': root_type,
                        'children': build_tree(root_id)
                    }
                    
                    return jsonify({'tree': tree})
                    
            except Exception as e:
                return jsonify({'error': str(e)}), 500
        
        # Tag-related routes
        @self.app.route('/api/tags')
        def get_tags():
            try:
                if not self.docs_db_path or not Path(self.docs_db_path).exists():
                    return jsonify({'tags': [], 'error': 'Documentation database not found'})
                
                with sqlite3.connect(self.docs_db_path) as conn:
                    cursor = conn.cursor()
                    
                    # Check if tags table exists
                    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='tags'")
                    if not cursor.fetchone():
                        return jsonify({'tags': [], 'error': 'Tags table not found'})
                    
                    cursor.execute("""
                        SELECT name, slug FROM tags 
                        ORDER BY name
                    """)
                    
                    tags = [{'name': row[0], 'slug': row[1]} for row in cursor.fetchall()]
                    return jsonify({'tags': tags})
                    
            except Exception as e:
                return jsonify({'error': str(e)}), 500
        
        @self.app.route('/api/tag-tree')
        def get_tag_tree():
            project = request.args.get('project', 'default')
            
            try:
                if not self.docs_db_path or not Path(self.docs_db_path).exists():
                    return jsonify({'tags': [], 'error': 'Documentation database not found'})
                
                with sqlite3.connect(self.docs_db_path) as conn:
                    cursor = conn.cursor()
                    
                    # Check if required tables exist
                    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name IN ('tags', 'projects')")
                    existing_tables = [row[0] for row in cursor.fetchall()]
                    
                    if 'tags' not in existing_tables or 'projects' not in existing_tables:
                        return jsonify({'tags': [], 'error': 'Required tables not found'})
                    
                    # Get project ID
                    cursor.execute("SELECT id FROM projects WHERE slug = ?", (project,))
                    project_row = cursor.fetchone()
                    if not project_row:
                        return jsonify({'tags': [], 'error': f'Project "{project}" not found'})
                    
                    project_id = project_row[0]
                    
                    def build_tag_tree(parent_id):
                        cursor.execute("""
                            SELECT id, name, slug, color,
                                   (SELECT COUNT(*) FROM property_tags WHERE tag_id = tags.id) as property_count
                            FROM tags 
                            WHERE parent_tag_id IS ? AND project_id = ?
                            ORDER BY sort_order, name
                        """, (parent_id, project_id))
                        
                        children = []
                        for row in cursor.fetchall():
                            tag_id, name, slug, color, prop_count = row
                            child = {
                                'id': tag_id,
                                'name': name,
                                'slug': slug,
                                'color': color,
                                'property_count': prop_count,
                                'children': build_tag_tree(tag_id)
                            }
                            children.append(child)
                        
                        return children
                    
                    tags = build_tag_tree(None)
                    return jsonify({'tags': tags})
                    
            except Exception as e:
                return jsonify({'error': str(e)}), 500
        
        # Project-related routes
        @self.app.route('/api/projects')
        def get_projects():
            try:
                with sqlite3.connect(self.docs_db_path) as conn:
                    cursor = conn.cursor()
                    
                    cursor.execute("""
                        SELECT p.id, p.name, p.slug, p.is_active, p.created_at,
                               (SELECT COUNT(*) FROM properties pr 
                                JOIN property_tags pt ON pr.id = pt.property_id 
                                JOIN tags t ON pt.tag_id = t.id 
                                WHERE t.project_id = p.id AND pr.status = 'active') as property_count,
                               (SELECT COUNT(*) FROM tags WHERE project_id = p.id) as tag_count
                        FROM projects p
                        ORDER BY p.created_at DESC
                    """)
                    
                    projects = []
                    for row in cursor.fetchall():
                        project_id, name, slug, is_active, created_at, prop_count, tag_count = row
                        projects.append({
                            'id': project_id,
                            'name': name,
                            'slug': slug,
                            'is_active': bool(is_active),
                            'property_count': prop_count,
                            'tag_count': tag_count,
                            'created_at': created_at
                        })
                    
                    return jsonify({'projects': projects})
                    
            except Exception as e:
                return jsonify({'error': str(e)}), 500
        
        
        # Statistics routes
        @self.app.route('/api/database-stats')
        def get_database_stats():
            try:
                stats = {}
                
                # OpenRecall stats
                if Path(self.recall_db_path).exists():
                    with sqlite3.connect(self.recall_db_path) as conn:
                        cursor = conn.cursor()
                        
                        cursor.execute("SELECT COUNT(*) FROM entries")
                        stats['total_entries'] = cursor.fetchone()[0]
                        
                        cursor.execute("SELECT COUNT(DISTINCT app) FROM entries")
                        stats['unique_apps'] = cursor.fetchone()[0]
                        
                        cursor.execute("SELECT MIN(timestamp), MAX(timestamp) FROM entries")
                        min_ts, max_ts = cursor.fetchone()
                        if min_ts and max_ts:
                            stats['days_of_data'] = round((max_ts - min_ts) / 86400, 1)
                        else:
                            stats['days_of_data'] = 0
                
                # Documentation stats
                if Path(self.docs_db_path).exists():
                    with sqlite3.connect(self.docs_db_path) as conn:
                        cursor = conn.cursor()
                        
                        # Properties stats
                        cursor.execute("SELECT COUNT(*) FROM properties WHERE status = 'active'")
                        stats['total_properties'] = cursor.fetchone()[0]
                        
                        cursor.execute("SELECT type, COUNT(*) FROM properties WHERE status = 'active' GROUP BY type")
                        stats['properties_by_type'] = {row[0]: row[1] for row in cursor.fetchall()}
                        
                        # Other stats
                        cursor.execute("SELECT COUNT(*) FROM tags")
                        stats['total_tags'] = cursor.fetchone()[0]
                        
                        cursor.execute("SELECT COUNT(*) FROM projects WHERE is_active = 1")
                        stats['active_projects'] = cursor.fetchone()[0]
                        
                        cursor.execute("SELECT COUNT(*) FROM versions")
                        stats['total_versions'] = cursor.fetchone()[0]
                        
                        cursor.execute("SELECT COUNT(*) FROM search_index")
                        indexed_properties = cursor.fetchone()[0]
                        stats['indexed_properties'] = indexed_properties
                        
                        total_props = stats.get('total_properties', 0)
                        stats['index_coverage'] = round(indexed_properties / max(total_props, 1) * 100, 1)
                        
                        # Database size
                        stats['size_mb'] = round(Path(self.docs_db_path).stat().st_size / 1024 / 1024, 2)
                
                return jsonify(stats)
                
            except Exception as e:
                return jsonify({'error': str(e)}), 500
        
        @self.app.route('/api/rebuild-search-index', methods=['POST'])
        def rebuild_search_index():
            try:
                # This would need to integrate with the DocumentationMCP rebuild functionality
                # For now, return a placeholder response
                return jsonify({
                    'success': True,
                    'message': 'Search index rebuild requested (placeholder)'
                })
                
            except Exception as e:
                return jsonify({'error': str(e)}), 500
        
        # Configuration management routes
        @self.app.route('/api/config')
        def get_config():
            try:
                reload_config = request.args.get('reload', 'false').lower() == 'true'
                if reload_config:
                    self.config = self.load_config()
                    # Update paths
                    self.recall_db_path = self.config.get('database', 'recall_db_path', fallback=None)
                    self.docs_db_path = self.config.get('database', 'docs_db_path', fallback='documentation.db')
                
                # Get database status
                recall_status = self.get_database_status(self.recall_db_path)
                docs_status = self.get_database_status(self.docs_db_path)
                
                return jsonify({
                    'recall_db_path': self.recall_db_path or '',
                    'docs_db_path': self.docs_db_path or '',
                    'recall_db_status': recall_status,
                    'docs_db_status': docs_status,
                    'server': {
                        'host': self.config.get('server', 'host'),
                        'port': self.config.getint('server', 'port')
                    },
                    'interface': {
                        'auto_refresh_seconds': self.config.getint('interface', 'auto_refresh_seconds'),
                        'default_page_size': self.config.getint('interface', 'default_page_size')
                    },
                    'last_updated': self.config.get('metadata', 'last_updated', fallback='Never'),
                    'version': self.config.get('metadata', 'version', fallback='Unknown'),
                    'config_file': str(Path(self.config_path).absolute())
                })
                
            except Exception as e:
                return jsonify({'error': str(e)}), 500
        
        @self.app.route('/api/config', methods=['POST'])
        def update_config():
            try:
                data = request.get_json()
                
                if not data:
                    return jsonify({'error': 'No configuration data provided'}), 400
                
                # Validate required fields
                if 'recall_db_path' not in data:
                    return jsonify({'error': 'recall_db_path is required'}), 400
                
                # Update configuration
                self.config.set('database', 'recall_db_path', data.get('recall_db_path', ''))
                self.config.set('database', 'docs_db_path', data.get('docs_db_path', 'documentation.db'))
                
                if 'server' in data:
                    self.config.set('server', 'host', str(data['server'].get('host', '127.0.0.1')))
                    self.config.set('server', 'port', str(data['server'].get('port', 8084)))
                
                if 'interface' in data:
                    self.config.set('interface', 'auto_refresh_seconds', str(data['interface'].get('auto_refresh_seconds', 30)))
                    self.config.set('interface', 'default_page_size', str(data['interface'].get('default_page_size', 20)))
                
                # Save configuration
                if self.save_config():
                    # Update instance variables
                    self.recall_db_path = self.config.get('database', 'recall_db_path', fallback=None)
                    self.docs_db_path = self.config.get('database', 'docs_db_path', fallback='documentation.db')
                    
                    return jsonify({'success': True, 'message': 'Configuration updated successfully'})
                else:
                    return jsonify({'error': 'Failed to save configuration'}), 500
                    
            except Exception as e:
                return jsonify({'error': str(e)}), 500
        
        @self.app.route('/api/config/reset', methods=['POST'])
        def reset_config():
            try:
                # Create backup of current config
                backup_path = self.config_path + '.backup'
                if Path(self.config_path).exists():
                    shutil.copy2(self.config_path, backup_path)
                
                # Reset to defaults
                self.config = self.load_config()
                
                # Remove the existing file to force creation of defaults
                if Path(self.config_path).exists():
                    Path(self.config_path).unlink()
                
                # Reload with defaults
                self.config = self.load_config()
                
                # Update instance variables
                self.recall_db_path = self.config.get('database', 'recall_db_path', fallback=None)
                self.docs_db_path = self.config.get('database', 'docs_db_path', fallback='documentation.db')
                
                return jsonify({
                    'success': True, 
                    'message': f'Configuration reset to defaults. Backup saved as {backup_path}'
                })
                
            except Exception as e:
                return jsonify({'error': str(e)}), 500


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Database Viewer Interface - Property-Based Schema")
    parser.add_argument('--config', default='database_viewer.ini', help='Path to configuration file')
    parser.add_argument('--recall-db', help='Path to OpenRecall database (overrides config)')
    parser.add_argument('--docs-db', help='Path to documentation database (overrides config)')
    parser.add_argument('--port', type=int, help='Port to run on (overrides config)')
    parser.add_argument('--host', help='Host to bind to (overrides config)')
    parser.add_argument('--create-config', action='store_true', help='Create default configuration file and exit')
    
    args = parser.parse_args()
    
    # Create default config and exit
    if args.create_config:
        viewer = DatabaseViewer(config_path=args.config)
        print(f"Configuration file created: {Path(args.config).absolute()}")
        print("Please edit the configuration file and run again.")
        return 0
    
    # Initialize viewer with config
    viewer = DatabaseViewer(
        config_path=args.config,
        recall_db_path=args.recall_db,
        docs_db_path=args.docs_db
    )
    
    # Get server settings from config or command line
    host = args.host or viewer.config.get('server', 'host', fallback='127.0.0.1')
    port = args.port or viewer.config.getint('server', 'port', fallback=8084)
    
    # Validate critical paths
    if not viewer.recall_db_path:
        print("ERROR: OpenRecall database path not configured.")
        print("Please set recall_db_path in the configuration file or use --recall-db argument.")
        print(f"Configuration file: {Path(args.config).absolute()}")
        return 1
    
    if not os.path.exists(viewer.recall_db_path):
        print(f"ERROR: OpenRecall database not found: {viewer.recall_db_path}")
        print("Please check the path in your configuration file or create the database.")
        return 1
    
    print(f"Starting Database Viewer v2.0 on http://{host}:{port}")
    print(f"Configuration file: {Path(args.config).absolute()}")
    print(f"OpenRecall DB: {viewer.recall_db_path}")
    print(f"Documentation DB: {viewer.docs_db_path}")
    print("Features: Property-based schema, hierarchical data, tag management, full-text search, configurable settings")
    
    try:
        viewer.app.run(host=host, port=port, debug=False)
    except KeyboardInterrupt:
        print("\nShutting down gracefully...")
    except Exception as e:
        print(f"Error starting server: {e}")
        return 1
        
    return 0


if __name__ == "__main__":
    exit(main())