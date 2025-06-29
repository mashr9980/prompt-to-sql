class DatabaseQueryApp {
    constructor() {
        this.baseURL = this.getBaseURL();
        this.init();
    }

    getBaseURL() {
        if (window.location.protocol === 'file:') {
            return 'https://tx5npat3ybvphq-8000.proxy.runpod.net';
        }
        return window.location.origin;
    }

    init() {
        this.bindEvents();
        this.checkSystemHealth();
        this.setActiveSection('query');
    }

    bindEvents() {
        document.querySelectorAll('.nav-item').forEach(item => {
            item.addEventListener('click', (e) => {
                const section = e.currentTarget.dataset.section;
                this.setActiveSection(section);
            });
        });

        document.getElementById('queryBtn').addEventListener('click', () => {
            this.executeQuery();
        });

        document.getElementById('executeSqlBtn').addEventListener('click', () => {
            this.executeSqlQuery();
        });

        document.getElementById('formatSqlBtn').addEventListener('click', () => {
            this.formatSql();
        });

        document.getElementById('clearSqlBtn').addEventListener('click', () => {
            document.getElementById('sqlInput').value = '';
        });

        document.getElementById('loadTablesBtn').addEventListener('click', () => {
            this.loadDatabaseInfo();
        });

        document.getElementById('checkHealthBtn').addEventListener('click', () => {
            this.checkDetailedHealth();
        });

        document.getElementById('quickHealthBtn').addEventListener('click', () => {
            this.checkQuickHealth();
        });

        document.getElementById('copyResult').addEventListener('click', () => {
            this.copyToClipboard('queryResultContent');
        });

        document.getElementById('clearResults').addEventListener('click', () => {
            this.clearResults('queryResults');
        });

        document.getElementById('copySqlResult').addEventListener('click', () => {
            this.copyToClipboard('sqlResultContent');
        });

        document.getElementById('clearSqlResults').addEventListener('click', () => {
            this.clearResults('sqlResults');
        });

        document.querySelectorAll('.suggestion-btn').forEach(btn => {
            btn.addEventListener('click', (e) => {
                const query = e.currentTarget.dataset.query;
                document.getElementById('queryInput').value = query;
            });
        });

        document.querySelectorAll('.toast-close').forEach(btn => {
            btn.addEventListener('click', (e) => {
                this.hideToast(e.currentTarget.parentElement);
            });
        });

        document.getElementById('queryInput').addEventListener('keydown', (e) => {
            if (e.ctrlKey && e.key === 'Enter') {
                this.executeQuery();
            }
        });

        document.getElementById('sqlInput').addEventListener('keydown', (e) => {
            if (e.ctrlKey && e.key === 'Enter') {
                this.executeSqlQuery();
            }
        });
    }

    setActiveSection(sectionName) {
        document.querySelectorAll('.nav-item').forEach(item => {
            item.classList.remove('active');
        });
        
        document.querySelectorAll('.section').forEach(section => {
            section.classList.remove('active');
        });

        document.querySelector(`[data-section="${sectionName}"]`).classList.add('active');
        document.getElementById(`${sectionName}Section`).classList.add('active');
    }

    showLoading() {
        document.getElementById('loadingOverlay').classList.remove('hidden');
    }

    hideLoading() {
        document.getElementById('loadingOverlay').classList.add('hidden');
    }

    showToast(message, type = 'success') {
        const toast = document.getElementById(`${type}Toast`);
        const messageElement = toast.querySelector('.toast-message');
        
        messageElement.textContent = message;
        toast.classList.remove('hidden');
        toast.classList.add('show');

        setTimeout(() => {
            this.hideToast(toast);
        }, 5000);
    }

    hideToast(toast) {
        toast.classList.remove('show');
        setTimeout(() => {
            toast.classList.add('hidden');
        }, 300);
    }

    async makeRequest(endpoint, options = {}) {
        try {
            const response = await fetch(`${this.baseURL}${endpoint}`, {
                headers: {
                    'Content-Type': 'application/json',
                    ...options.headers
                },
                ...options
            });

            if (!response.ok) {
                let errorMessage;
                try {
                    const errorData = await response.json();
                    errorMessage = errorData.detail || errorData.message || `HTTP ${response.status}`;
                } catch {
                    errorMessage = `HTTP ${response.status}: ${response.statusText}`;
                }
                throw new Error(errorMessage);
            }

            const data = await response.json();
            return data;
        } catch (error) {
            if (error.name === 'TypeError' && error.message.includes('fetch')) {
                throw new Error('Network error: Unable to connect to server');
            }
            throw error;
        }
    }

    async executeQuery() {
        const queryInput = document.getElementById('queryInput');
        const includeSql = document.getElementById('includeSql');
        const resultsContainer = document.getElementById('queryResults');
        const resultContent = document.getElementById('queryResultContent');

        const query = queryInput.value.trim();
        if (!query) {
            this.showToast('Please enter a query', 'error');
            return;
        }

        this.showLoading();
        
        try {
            const response = await this.makeRequest('/api/query', {
                method: 'POST',
                body: JSON.stringify({
                    command: query,
                    include_sql: includeSql.checked
                })
            });

            this.displaySqlOnlyResult(response, resultContent);
            resultsContainer.classList.remove('hidden');
            resultsContainer.scrollIntoView({ behavior: 'smooth' });

            if (response.success) {
                this.showToast('SQL query generated successfully');
            } else {
                this.showToast('Query generation failed', 'error');
            }

        } catch (error) {
            this.displayError(error.message, resultContent);
            resultsContainer.classList.remove('hidden');
            this.showToast(`Query failed: ${error.message}`, 'error');
        } finally {
            this.hideLoading();
        }
    }

    async executeSqlQuery() {
        const sqlInput = document.getElementById('sqlInput');
        const resultsContainer = document.getElementById('sqlResults');
        const resultContent = document.getElementById('sqlResultContent');

        const query = sqlInput.value.trim();
        if (!query) {
            this.showToast('Please enter a SQL query', 'error');
            return;
        }

        this.showLoading();
        
        try {
            const response = await this.makeRequest('/api/query/sql', {
                method: 'POST',
                body: JSON.stringify({
                    sql_query: query
                })
            });

            this.displaySqlExecutionResult(response, resultContent);
            resultsContainer.classList.remove('hidden');
            resultsContainer.scrollIntoView({ behavior: 'smooth' });

            if (response.success) {
                this.showToast('SQL executed successfully');
            } else {
                this.showToast('SQL execution failed', 'error');
            }

        } catch (error) {
            this.displayError(error.message, resultContent);
            resultsContainer.classList.remove('hidden');
            this.showToast(`SQL execution failed: ${error.message}`, 'error');
        } finally {
            this.hideLoading();
        }
    }

    async loadDatabaseInfo() {
        const infoContainer = document.getElementById('databaseInfo');
        const tablesContainer = document.getElementById('tablesList');

        this.showLoading();
        
        try {
            const response = await this.makeRequest('/api/database/tables');

            if (response.table_names && response.table_names.length > 0) {
                this.displayTables(response.table_names, tablesContainer);
                infoContainer.classList.remove('hidden');
                this.showToast(`Loaded ${response.table_names.length} tables`);
            } else {
                this.displayEmptyState(tablesContainer, 'No tables found');
                infoContainer.classList.remove('hidden');
            }

        } catch (error) {
            this.displayError(error.message, tablesContainer);
            infoContainer.classList.remove('hidden');
            this.showToast(`Failed to load database info: ${error.message}`, 'error');
        } finally {
            this.hideLoading();
        }
    }

    async loadTableDetails(tableName) {
        const detailsContainer = document.getElementById('tableDetails');
        const schemaContainer = document.getElementById('tableSchema');

        this.showLoading();
        
        try {
            const response = await this.makeRequest(`/api/database/tables/${encodeURIComponent(tableName)}`);

            if (response.schema) {
                schemaContainer.textContent = response.schema;
                detailsContainer.classList.remove('hidden');
                this.showToast(`Loaded schema for ${tableName}`);
            } else {
                this.displayError(response.error || 'No schema found', schemaContainer);
                detailsContainer.classList.remove('hidden');
            }

        } catch (error) {
            this.displayError(error.message, schemaContainer);
            detailsContainer.classList.remove('hidden');
            this.showToast(`Failed to load table details: ${error.message}`, 'error');
        } finally {
            this.hideLoading();
        }
    }

    async checkSystemHealth() {
        try {
            const response = await this.makeRequest('/api/health/quick');
            this.updateStatusIndicator(response.status === 'healthy');
        } catch (error) {
            this.updateStatusIndicator(false);
        }
    }

    async checkQuickHealth() {
        this.showLoading();
        
        try {
            const response = await this.makeRequest('/api/health/quick');
            this.displayQuickHealth(response);
            this.showToast('Quick health check completed');
        } catch (error) {
            this.showToast(`Health check failed: ${error.message}`, 'error');
        } finally {
            this.hideLoading();
        }
    }

    async checkDetailedHealth() {
        const resultsContainer = document.getElementById('healthResults');
        
        this.showLoading();
        
        try {
            const response = await this.makeRequest('/api/health');
            this.displayDetailedHealth(response);
            resultsContainer.classList.remove('hidden');
            this.showToast('Detailed health check completed');
        } catch (error) {
            this.displayHealthError(error.message);
            resultsContainer.classList.remove('hidden');
            this.showToast(`Health check failed: ${error.message}`, 'error');
        } finally {
            this.hideLoading();
        }
    }

    updateStatusIndicator(isOnline) {
        const indicator = document.getElementById('statusIndicator');
        const text = indicator.querySelector('span');
        
        if (isOnline) {
            indicator.classList.remove('offline');
            indicator.classList.add('online');
            text.textContent = 'Online';
        } else {
            indicator.classList.remove('online');
            indicator.classList.add('offline');
            text.textContent = 'Offline';
        }
    }

    displaySqlOnlyResult(response, container) {
        const resultItem = document.createElement('div');
        resultItem.className = 'result-content fade-in';

        if (response.success) {
            let content = `<div class="result-item">`;
            
            content += `
                <h4><i class="fas fa-code"></i> Generated SQL Query</h4>
                <div class="sql-query-container">
                    <pre class="sql-query">${this.escapeHtml(response.sql_query || 'No SQL generated')}</pre>
                    <div class="sql-actions">
                        <button class="btn-secondary copy-sql-btn" onclick="app.copyGeneratedSql('${this.escapeForAttribute(response.sql_query || '')}')">
                            <i class="fas fa-copy"></i> Copy SQL
                        </button>
                        <button class="btn-secondary test-sql-btn" onclick="app.moveToSqlTab('${this.escapeForAttribute(response.sql_query || '')}')">
                            <i class="fas fa-play"></i> Test Query
                        </button>
                    </div>
                </div>
                <div class="execution-time">Generation time: ${response.execution_time}s</div>
                <div class="sql-note">
                    <i class="fas fa-info-circle"></i>
                    Use the "Test Query" button to execute this SQL and see the results.
                </div>
            </div>`;
            
            resultItem.innerHTML = content;
        } else {
            resultItem.innerHTML = `
                <div class="error-message">
                    <i class="fas fa-exclamation-triangle"></i>
                    <strong>Error:</strong> ${this.escapeHtml(response.error)}
                    <div class="execution-time">Generation time: ${response.execution_time}s</div>
                </div>
            `;
        }

        container.innerHTML = '';
        container.appendChild(resultItem);
    }

    displaySqlExecutionResult(response, container) {
        const resultItem = document.createElement('div');
        resultItem.className = 'result-content fade-in';

        if (response.success) {
            const content = `
                <div class="result-item">
                    <h4><i class="fas fa-database"></i> SQL Execution Completed</h4>
                    <div class="sql-executed">
                        <strong>Query:</strong>
                        <pre class="sql-query">${this.escapeHtml(response.sql_query)}</pre>
                    </div>
                    <div class="execution-time">Execution time: ${response.execution_time}s</div>
                    <div class="success-message">
                        <i class="fas fa-check-circle"></i>
                        SQL query executed successfully. Check your database for results.
                    </div>
                </div>
            `;
            resultItem.innerHTML = content;
        } else {
            resultItem.innerHTML = `
                <div class="error-message">
                    <i class="fas fa-exclamation-triangle"></i>
                    <strong>SQL Error:</strong> ${this.escapeHtml(response.error)}
                    <div class="execution-time">Execution time: ${response.execution_time}s</div>
                </div>
            `;
        }

        container.innerHTML = '';
        container.appendChild(resultItem);
    }

    displayTables(tables, container) {
        container.innerHTML = '';
        
        tables.forEach(tableName => {
            const tableCard = document.createElement('div');
            tableCard.className = 'table-card slide-in';
            tableCard.innerHTML = `
                <h4><i class="fas fa-table"></i> ${this.escapeHtml(tableName)}</h4>
                <p>Click to view schema</p>
            `;
            
            tableCard.addEventListener('click', () => {
                document.querySelectorAll('.table-card').forEach(card => {
                    card.classList.remove('active');
                });
                tableCard.classList.add('active');
                this.loadTableDetails(tableName);
            });
            
            container.appendChild(tableCard);
        });
    }

    displayDetailedHealth(response) {
        const systemCard = document.getElementById('systemStatus');
        const databaseCard = document.getElementById('databaseStatus');
        const tablesCard = document.getElementById('tablesCount');

        this.updateHealthCard(systemCard, response.status, response.status === 'healthy' ? 'Healthy' : 'Unhealthy');
        this.updateHealthCard(databaseCard, response.database_connected ? 'healthy' : 'unhealthy', 
                             response.database_connected ? 'Connected' : 'Disconnected');
        
        if (response.tables_count !== undefined) {
            this.updateHealthCard(tablesCard, 'healthy', `${response.tables_count} Tables`);
        } else {
            this.updateHealthCard(tablesCard, 'unknown', 'Unknown');
        }
    }

    displayQuickHealth(response) {
        this.showToast(`System: ${response.status}, Database: ${response.database_connected ? 'Connected' : 'Disconnected'}`);
    }

    updateHealthCard(card, status, text) {
        const statusText = card.querySelector('.status-text');
        
        card.classList.remove('healthy', 'unhealthy');
        statusText.classList.remove('healthy', 'unhealthy');
        
        if (status === 'healthy') {
            card.classList.add('healthy');
            statusText.classList.add('healthy');
        } else if (status === 'unhealthy') {
            card.classList.add('unhealthy');
            statusText.classList.add('unhealthy');
        }
        
        statusText.textContent = text;
    }

    displayHealthError(error) {
        const resultsContainer = document.getElementById('healthResults');
        resultsContainer.innerHTML = `
            <div class="error-message">
                <i class="fas fa-exclamation-triangle"></i>
                <strong>Health Check Failed:</strong> ${this.escapeHtml(error)}
            </div>
        `;
    }

    displayError(error, container) {
        container.innerHTML = `
            <div class="error-message">
                <i class="fas fa-exclamation-triangle"></i>
                <strong>Error:</strong> ${this.escapeHtml(error)}
            </div>
        `;
    }

    displayEmptyState(container, message) {
        container.innerHTML = `
            <div class="empty-state">
                <i class="fas fa-inbox"></i>
                <h3>No Data</h3>
                <p>${this.escapeHtml(message)}</p>
            </div>
        `;
    }

    formatSql() {
        const sqlInput = document.getElementById('sqlInput');
        const query = sqlInput.value;
        
        if (!query.trim()) {
            this.showToast('No SQL to format', 'error');
            return;
        }

        try {
            const formatted = this.basicSqlFormat(query);
            sqlInput.value = formatted;
            this.showToast('SQL formatted successfully');
        } catch (error) {
            this.showToast('Failed to format SQL', 'error');
        }
    }

    basicSqlFormat(sql) {
        return sql
            .replace(/\s+/g, ' ')
            .replace(/,\s*/g, ',\n    ')
            .replace(/\bSELECT\b/gi, 'SELECT')
            .replace(/\bFROM\b/gi, '\nFROM')
            .replace(/\bWHERE\b/gi, '\nWHERE')
            .replace(/\bAND\b/gi, '\n  AND')
            .replace(/\bOR\b/gi, '\n  OR')
            .replace(/\bORDER BY\b/gi, '\nORDER BY')
            .replace(/\bGROUP BY\b/gi, '\nGROUP BY')
            .replace(/\bHAVING\b/gi, '\nHAVING')
            .replace(/\bJOIN\b/gi, '\nJOIN')
            .replace(/\bINNER JOIN\b/gi, '\nINNER JOIN')
            .replace(/\bLEFT JOIN\b/gi, '\nLEFT JOIN')
            .replace(/\bRIGHT JOIN\b/gi, '\nRIGHT JOIN')
            .trim();
    }

    async copyToClipboard(elementId) {
        try {
            const element = document.getElementById(elementId);
            const text = element.textContent || element.innerText;
            
            if (navigator.clipboard) {
                await navigator.clipboard.writeText(text);
            } else {
                const textArea = document.createElement('textarea');
                textArea.value = text;
                document.body.appendChild(textArea);
                textArea.select();
                document.execCommand('copy');
                document.body.removeChild(textArea);
            }
            
            this.showToast('Copied to clipboard');
        } catch (error) {
            this.showToast('Failed to copy to clipboard', 'error');
        }
    }

    async copyGeneratedSql(sqlQuery) {
        try {
            if (navigator.clipboard) {
                await navigator.clipboard.writeText(sqlQuery);
            } else {
                const textArea = document.createElement('textarea');
                textArea.value = sqlQuery;
                document.body.appendChild(textArea);
                textArea.select();
                document.execCommand('copy');
                document.body.removeChild(textArea);
            }
            
            this.showToast('SQL copied to clipboard');
        } catch (error) {
            this.showToast('Failed to copy SQL', 'error');
        }
    }

    moveToSqlTab(sqlQuery) {
        this.setActiveSection('sql');
        
        document.getElementById('sqlInput').value = sqlQuery;
        
        document.getElementById('sqlInput').focus();
        
        this.showToast('SQL moved to Direct SQL tab for testing');
    }

    clearResults(containerId) {
        const container = document.getElementById(containerId);
        container.classList.add('hidden');
        const content = container.querySelector('[id$="Content"]');
        if (content) {
            content.innerHTML = '';
        }
    }

    escapeHtml(text) {
        if (text === null || text === undefined) return '';
        return String(text)
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;')
            .replace(/"/g, '&quot;')
            .replace(/'/g, '&#039;');
    }

    escapeForAttribute(text) {
        if (text === null || text === undefined) return '';
        return String(text)
            .replace(/"/g, '&quot;')
            .replace(/'/g, '&#x27;')
            .replace(/\\/g, '\\\\')
            .replace(/\n/g, '\\n')
            .replace(/\r/g, '\\r');
    }
}

let app;

document.addEventListener('DOMContentLoaded', () => {
    try {
        app = new DatabaseQueryApp();
    } catch (error) {
        console.error('Failed to initialize app:', error);
        document.body.innerHTML = `
            <div class="error-message" style="margin: 2rem; padding: 2rem; border-radius: 12px;">
                <h2>Application Error</h2>
                <p>Failed to initialize the application: ${error.message}</p>
                <p>Please refresh the page and try again.</p>
            </div>
        `;
    }
});