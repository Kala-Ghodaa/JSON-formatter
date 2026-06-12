/**
 * JSON Tools - Professional JSON Editor & Formatter
 * A fully client-side JSON tools web application
 */

// State Management
const state = {
    input: '',
    output: '',
    parsedJson: null,
    isValid: false,
    theme: 'light',
    indentSize: 2,
    searchMatches: [],
    currentSearchIndex: -1,
    isTreeView: false,
    validateTimeout: null,
    replaceMatches: [],
    selectedNode: null,
    selectedNodePath: '',
    selectedNodeValue: null,
    filteredJson: null
};

// DOM Elements
const elements = {};

function initElements() {
    elements.inputEditor = document.getElementById('inputEditor');
    elements.outputEditor = document.getElementById('outputEditor');
    elements.inputLineNumbers = document.getElementById('inputLineNumbers');
    elements.outputLineNumbers = document.getElementById('outputLineNumbers');
    elements.treeView = document.getElementById('treeView');
    elements.leftPanel = document.getElementById('leftPanel');
    elements.resizer = document.getElementById('resizer');
    elements.searchPanel = document.getElementById('searchPanel');
    elements.comparePanel = document.getElementById('comparePanel');
    elements.inputStats = document.getElementById('inputStats');
    elements.outputStats = document.getElementById('outputStats');
    elements.validationStatus = document.getElementById('validationStatus');
    elements.statusMessage = document.getElementById('statusMessage');
    elements.formatBtn = document.getElementById('formatBtn');
    elements.minifyBtn = document.getElementById('minifyBtn');
    elements.validateBtn = document.getElementById('validateBtn');
    elements.fixBtn = document.getElementById('fixBtn');
    elements.treeViewBtn = document.getElementById('treeViewBtn');
    elements.compareBtn = document.getElementById('compareBtn');
    elements.searchBtn = document.getElementById('searchBtn');
    elements.jmespathBtn = document.getElementById('jmespathBtn');
    elements.downloadBtn = document.getElementById('downloadBtn');
    elements.copyBtn = document.getElementById('copyBtn');
    elements.convertBtn = document.getElementById('convertBtn');
    elements.clearInputBtn = document.getElementById('clearInputBtn');
    elements.expandAllBtn = document.getElementById('expandAllBtn');
    elements.collapseAllBtn = document.getElementById('collapseAllBtn');
    elements.themeToggle = document.getElementById('themeToggle');
    elements.searchInput = document.getElementById('searchInput');
    elements.replaceInput = document.getElementById('replaceInput');
    elements.replaceBtn = document.getElementById('replaceBtn');
    elements.replaceAllBtn = document.getElementById('replaceAllBtn');
    elements.searchNextBtn = document.getElementById('searchNextBtn');
    elements.searchPrevBtn = document.getElementById('searchPrevBtn');
    elements.searchCount = document.getElementById('searchCount');
    elements.closeSearchBtn = document.getElementById('closeSearchBtn');
    elements.jmespathPanel = document.getElementById('jmespathPanel');
    elements.jmespathQuery = document.getElementById('jmespathQuery');
    elements.filterKey = document.getElementById('filterKey');
    elements.runJmespathBtn = document.getElementById('runJmespathBtn');
    elements.applyFilterBtn = document.getElementById('applyFilterBtn');
    elements.closeJmespathBtn = document.getElementById('closeJmespathBtn');
    elements.jmespathResults = document.getElementById('jmespathResults');
    elements.compareJson1 = document.getElementById('compareJson1');
    elements.compareJson2 = document.getElementById('compareJson2');
    elements.compareResults = document.getElementById('compareResults');
    elements.doCompareBtn = document.getElementById('doCompareBtn');
    elements.closeCompareBtn = document.getElementById('closeCompareBtn');
    elements.convertDropdown = document.getElementById('convertDropdown');
    elements.indentSelect = document.getElementById('indentSelect');
    elements.fileInput = document.getElementById('fileInput');
    elements.convertModal = document.getElementById('convertModal');
    elements.convertOutput = document.getElementById('convertOutput');
    elements.convertModalTitle = document.getElementById('convertModalTitle');
    elements.closeConvertModal = document.getElementById('closeConvertModal');
    elements.copyConvertBtn = document.getElementById('copyConvertBtn');
    elements.downloadConvertBtn = document.getElementById('downloadConvertBtn');
    elements.toastContainer = document.getElementById('toastContainer');
    // Node actions bar elements
    elements.nodeActionsBar = document.getElementById('nodeActionsBar');
    elements.selectedNodePath = document.getElementById('selectedNodePath');
    elements.copyNodeBtn = document.getElementById('copyNodeBtn');
    elements.filterByNodeBtn = document.getElementById('filterByNodeBtn');
    elements.editNodeBtn = document.getElementById('editNodeBtn');
    elements.clearSelectionBtn = document.getElementById('clearSelectionBtn');
}

// Utility Functions
function showToast(message, type = 'info') {
    const toast = document.createElement('div');
    toast.className = `toast ${type}`;
    toast.textContent = message;
    elements.toastContainer.appendChild(toast);
    setTimeout(() => toast.remove(), 3000);
}

function setStatus(message) {
    elements.statusMessage.textContent = message;
}

function updateStats() {
    const inputText = elements.inputEditor.value;
    const outputText = elements.outputEditor.value;
    elements.inputStats.textContent = `${inputText.length.toLocaleString()} chars | ${inputText.split('\n').length} lines`;
    elements.outputStats.textContent = `${outputText.length.toLocaleString()} chars | ${outputText.split('\n').length} lines`;
}

function updateLineNumbers(textarea, lineNumbersEl) {
    const lines = textarea.value.split('\n').length;
    lineNumbersEl.innerHTML = Array.from({ length: Math.max(lines, 1) }, (_, i) => i + 1).join('<br>');
}

function syncLineNumbers() {
    updateLineNumbers(elements.inputEditor, elements.inputLineNumbers);
    updateLineNumbers(elements.outputEditor, elements.outputLineNumbers);
}

// JSON Processing
function validateJSON(str) {
    try {
        return { valid: true, data: JSON.parse(str), error: null };
    } catch (e) {
        return { valid: false, data: null, error: e.message };
    }
}

function formatJSON(indent = 2) {
    const input = elements.inputEditor.value.trim();
    if (!input) { showToast('Please enter JSON', 'warning'); return; }
    
    const result = validateJSON(input);
    if (!result.valid) {
        setValidationStatus(false, result.error);
        showToast('Invalid: ' + result.error, 'error');
        return;
    }
    
    const indentStr = indent === 'tab' ? '\t' : ' '.repeat(parseInt(indent));
    elements.outputEditor.value = JSON.stringify(result.data, null, indentStr);
    state.parsedJson = result.data;
    setValidationStatus(true);
    showToast('Formatted!', 'success');
    updateStats();
    syncLineNumbers();
}

function minifyJSON() {
    const input = elements.inputEditor.value.trim();
    if (!input) { showToast('Please enter JSON', 'warning'); return; }
    
    const result = validateJSON(input);
    if (!result.valid) {
        setValidationStatus(false, result.error);
        showToast('Invalid: ' + result.error, 'error');
        return;
    }
    
    elements.outputEditor.value = JSON.stringify(result.data);
    state.parsedJson = result.data;
    setValidationStatus(true);
    showToast('Minified!', 'success');
    updateStats();
    syncLineNumbers();
}

function setValidationStatus(valid, errorMsg = null) {
    state.isValid = valid;
    elements.validationStatus.className = 'validation-status ' + (valid ? 'valid' : 'invalid');
    elements.validationStatus.textContent = valid ? '✓ Valid' : '✗ Invalid';
    if (errorMsg) elements.validationStatus.title = errorMsg;
}

function fixJSON() {
    let input = elements.inputEditor.value.trim();
    if (!input) { showToast('Please enter JSON', 'warning'); return; }
    
    const fixes = [];
    
    // Fix single quotes
    if (input.includes("'")) {
        input = input.replace(/'/g, '"');
        fixes.push('quotes');
    }
    
    // Fix trailing commas
    if (/,\s*[\]}]/.test(input)) {
        input = input.replace(/,(\s*[\]}])/g, '$1');
        fixes.push('trailing commas');
    }
    
    // Quote unquoted keys
    input = input.replace(/([{,]\s*)([a-zA-Z_$][\w$]*)\s*:/g, '$1"$2":');
    if (fixes.length < 3) fixes.push('unquoted keys');
    
    // Fix Python None/True/False
    input = input.replace(/\bNone\b/g, 'null')
                 .replace(/\bTrue\b/g, 'true')
                 .replace(/\bFalse\b/g, 'false');
    
    elements.inputEditor.value = input;
    const result = validateJSON(input);
    
    if (result.valid) {
        setValidationStatus(true);
        showToast(`Fixed: ${fixes.join(', ')}`, 'success');
        formatJSON(state.indentSize);
    } else {
        setValidationStatus(false, result.error);
        showToast(`Applied fixes but still invalid`, 'warning');
    }
}

// Tree View
function renderTreeView(data, container, searchTerm = '') {
    container.innerHTML = '';

    function getType(val) {
        if (val === null) return 'null';
        if (Array.isArray(val)) return 'array';
        return typeof val;
    }

    function escapeHtml(str) {
        const div = document.createElement('div');
        div.textContent = str;
        return div.innerHTML;
    }

    function createNode(key, value, isRoot = false) {
        const node = document.createElement('div');
        node.className = 'tree-node' + (isRoot ? ' root' : '');

        const toggle = document.createElement('span');
        toggle.className = 'tree-toggle';
        node.appendChild(toggle);

        // Wrap content in a container for easier querying
        const contentDiv = document.createElement('span');
        contentDiv.className = 'tree-content';
        
        if (key !== null) {
            const keySpan = document.createElement('span');
            keySpan.className = 'tree-key';
            keySpan.textContent = `"${key}": `;
            if (searchTerm && String(key).toLowerCase().includes(searchTerm.toLowerCase())) {
                keySpan.classList.add('highlight');
            }
            contentDiv.appendChild(keySpan);
        }

        const type = getType(value);

        if (type === 'object' || type === 'array') {
            const isArray = type === 'array';
            const bracket = isArray ? '[' : '{';
            const closeBracket = isArray ? ']' : '}';
            const count = isArray ? value.length : Object.keys(value).length;

            const openBracket = document.createElement('span');
            openBracket.className = 'tree-bracket';
            openBracket.textContent = bracket;
            if (count === 0) openBracket.textContent += closeBracket;
            contentDiv.appendChild(openBracket);

            if (count > 0) {
                const children = document.createElement('div');
                children.className = 'tree-children';

                if (isArray) {
                    value.forEach((item, i) => children.appendChild(createNode(i, item)));
                } else {
                    Object.entries(value).forEach(([k, v]) => {
                        children.appendChild(createNode(k, v));
                    });
                }

                node.appendChild(children);
                const closeB = document.createElement('span');
                closeB.className = 'tree-bracket';
                closeB.textContent = closeBracket;
                contentDiv.appendChild(closeB);
            }
            
            node.appendChild(contentDiv);

            node.classList.add('expanded');
            toggle.addEventListener('click', () => {
                node.classList.toggle('expanded');
                node.classList.toggle('collapsed');
            });
        } else {
            const valSpan = document.createElement('span');
            valSpan.className = `tree-${type}`;
            let displayValue;
            if (type === 'string') {
                displayValue = `"${escapeHtml(value)}"`;
            } else if (type === 'null') {
                displayValue = 'null';
            } else {
                displayValue = String(value);
            }
            if (searchTerm && displayValue.toLowerCase().includes(searchTerm.toLowerCase())) {
                valSpan.classList.add('highlight');
            }
            valSpan.textContent = displayValue;
            contentDiv.appendChild(valSpan);
            node.appendChild(contentDiv);
            node.classList.add('leaf');
        }

        node.addEventListener('contextmenu', (e) => {
            e.preventDefault();
            showNodeContextMenu(e, key, value, node);
        });

        node.addEventListener('click', (e) => {
            if (e.target.classList.contains('tree-toggle') || e.target.classList.contains('tree-key')) return;
            // Select the node and show actions bar
            selectTreeNode(node, key, value);
        });

        return node;
    }

    container.appendChild(createNode(null, data, true));
}

// Select a tree node and show the actions bar
function selectTreeNode(nodeElement, key, value) {
    // Remove selection from previously selected node
    const prevSelected = elements.treeView.querySelector('.tree-node.selected');
    if (prevSelected) prevSelected.classList.remove('selected');
    
    // Add selection to current node
    nodeElement.classList.add('selected');
    
    // Store selection info
    state.selectedNode = nodeElement;
    state.selectedNodeValue = value;
    state.selectedNodePath = buildNodePath(nodeElement);
    
    // Update and show actions bar
    elements.selectedNodePath.textContent = state.selectedNodePath || 'root';
    elements.nodeActionsBar.style.display = 'flex';
    
    showToast('Node selected. Use the toolbar above for actions.', 'info');
}

// Build the path to a node (e.g., "users.0.email" or "config.settings.theme")
function buildNodePath(nodeElement) {
    const keys = [];
    let current = nodeElement;
    
    while (current && !current.classList.contains('root')) {
        // Find the key span in this node - look for direct child with tree-key class
        const keySpan = current.querySelector(':scope > .tree-content > .tree-key');
        if (keySpan) {
            let keyText = keySpan.textContent.trim();
            // Remove quotes and colon
            keyText = keyText.replace(/^"/, '').replace(/":?$/, '');
            if (keyText) {
                keys.unshift(keyText);
            }
        } else {
            // Check if this is an array index node
            const indexMatch = current.className.match(/array-item-(\d+)/);
            if (indexMatch) {
                keys.unshift(indexMatch[1]);
            }
        }
        
        // Move to parent tree-node
        const parent = current.parentElement?.closest('.tree-node');
        if (parent) {
            current = parent;
        } else {
            break;
        }
    }
    
    return keys.length > 0 ? keys.join('.') : 'root';
}

function showNodeContextMenu(e, key, value, nodeElement) {
    const menu = document.createElement('div');
    menu.className = 'context-menu';
    menu.style.position = 'absolute';
    menu.style.left = e.pageX + 'px';
    menu.style.top = e.pageY + 'px';
    menu.style.background = 'var(--bg-primary)';
    menu.style.border = '1px solid var(--border-color)';
    menu.style.borderRadius = '4px';
    menu.style.padding = '4px 0';
    menu.style.zIndex = '1000';
    menu.style.boxShadow = '0 2px 8px rgba(0,0,0,0.2)';

    const items = [
        { label: 'Copy Value', action: () => {
            navigator.clipboard.writeText(JSON.stringify(value, null, 2)).then(() => showToast('Copied!', 'success'));
        }},
        { label: 'Copy Path', action: () => {
            const path = getNodePath(nodeElement);
            navigator.clipboard.writeText(path).then(() => showToast('Path copied!', 'success'));
        }},
        { label: 'Filter by this Key', action: () => {
            if (key !== null) {
                filterByKey(String(key));
                elements.jmespathPanel.style.display = 'block';
                elements.filterKey.value = String(key);
            }
        }}
    ];

    items.forEach(item => {
        const btn = document.createElement('button');
        btn.textContent = item.label;
        btn.style.cssText = 'display:block;width:100%;padding:6px 12px;text-align:left;background:none;border:none;cursor:pointer;color:var(--text-primary);font-size:13px;';
        btn.addEventListener('click', () => {
            item.action();
            menu.remove();
        });
        btn.addEventListener('mouseenter', () => btn.style.background = 'var(--accent-color)');
        btn.addEventListener('mouseleave', () => btn.style.background = 'none');
        menu.appendChild(btn);
    });

    document.body.appendChild(menu);

    const closeMenu = () => {
        menu.remove();
        document.removeEventListener('click', closeMenu);
    };
    setTimeout(() => document.addEventListener('click', closeMenu), 10);
}

function getNodePath(nodeElement) {
    const keys = [];
    let current = nodeElement;
    while (current && !current.classList.contains('root')) {
        const prev = current.previousElementSibling;
        if (prev && prev.classList.contains('tree-key')) {
            const text = prev.textContent.replace('": ', '');
            keys.unshift(text);
        }
        current = current.parentElement?.closest('.tree-node');
    }
    return keys.join('.');
}

function toggleTreeView() {
    state.isTreeView = !state.isTreeView;
    
    if (state.isTreeView) {
        elements.treeView.style.display = 'block';
        elements.outputEditor.style.display = 'none';
        elements.outputLineNumbers.style.display = 'none';
        if (state.parsedJson) renderTreeView(state.parsedJson, elements.treeView);
    } else {
        elements.treeView.style.display = 'none';
        elements.outputEditor.style.display = 'block';
        elements.outputLineNumbers.style.display = 'block';
    }
    
    elements.expandAllBtn.style.display = state.isTreeView ? 'inline-block' : 'none';
    elements.collapseAllBtn.style.display = state.isTreeView ? 'inline-block' : 'none';
}

function expandAllTreeNodes() {
    elements.treeView.querySelectorAll('.tree-node').forEach(n => {
        n.classList.remove('collapsed');
        n.classList.add('expanded');
    });
}

function collapseAllTreeNodes() {
    elements.treeView.querySelectorAll('.tree-node:not(.leaf)').forEach(n => {
        n.classList.remove('expanded');
        n.classList.add('collapsed');
    });
}

// Search & Replace
function escapeRegex(str) {
    return str.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
}

function searchJSON(query) {
    if (!query) {
        state.searchMatches = [];
        state.currentSearchIndex = -1;
        elements.searchCount.textContent = '';
        highlightSearchMatches();
        return;
    }
    
    const text = elements.outputEditor.value;
    const regex = new RegExp(escapeRegex(query), 'gi');
    state.searchMatches = [];
    
    let match;
    while ((match = regex.exec(text)) !== null) {
        state.searchMatches.push({ index: match.index, text: match[0] });
    }
    
    state.currentSearchIndex = state.searchMatches.length > 0 ? 0 : -1;
    updateSearchCount();
    highlightSearchMatches();
    if (state.searchMatches.length > 0) goToSearchMatch(0);
}

function highlightSearchMatches() {
    if (state.isTreeView && state.parsedJson) {
        renderTreeView(state.parsedJson, elements.treeView, state.searchInput.value);
    }
}

function updateSearchCount() {
    if (state.searchMatches.length === 0) {
        elements.searchCount.textContent = 'No matches';
    } else {
        elements.searchCount.textContent = `${state.currentSearchIndex + 1}/${state.searchMatches.length}`;
    }
}

function goToSearchMatch(index) {
    if (state.searchMatches.length === 0) return;
    state.currentSearchIndex = ((index % state.searchMatches.length) + state.searchMatches.length) % state.searchMatches.length;
    updateSearchCount();
    const match = state.searchMatches[state.currentSearchIndex];
    elements.outputEditor.focus();
    elements.outputEditor.setSelectionRange(match.index, match.index + match.text.length);
}

function replaceCurrentMatch() {
    if (state.searchMatches.length === 0 || state.currentSearchIndex < 0) {
        showToast('No match selected', 'warning');
        return;
    }
    const replaceText = elements.replaceInput.value;
    const match = state.searchMatches[state.currentSearchIndex];
    const output = elements.outputEditor.value;
    
    const newText = output.substring(0, match.index) + replaceText + output.substring(match.index + match.text.length);
    elements.outputEditor.value = newText;
    
    searchJSON(state.searchInput.value);
    showToast('Replaced!', 'success');
    updateStats();
}

function replaceAllMatches() {
    if (state.searchMatches.length === 0) {
        showToast('No matches to replace', 'warning');
        return;
    }
    const query = state.searchInput.value;
    const replaceText = elements.replaceInput.value;
    const output = elements.outputEditor.value;
    
    const regex = new RegExp(escapeRegex(query), 'gi');
    const newText = output.replace(regex, replaceText);
    elements.outputEditor.value = newText;
    
    state.searchMatches = [];
    state.currentSearchIndex = -1;
    elements.searchCount.textContent = '';
    const count = (output.match(regex) || []).length;
    showToast(`Replaced ${count} occurrences`, 'success');
    searchJSON('');
    updateStats();
}

function toggleSearchPanel() {
    const visible = elements.searchPanel.style.display !== 'none';
    // Toggle: if closing, just hide; if opening, close others but allow re-opening without forcing close
    if (visible) {
        elements.searchPanel.style.display = 'none';
    } else {
        elements.searchPanel.style.display = 'flex';
        elements.searchInput.focus();
        // Close other panels to avoid overlap
        elements.jmespathPanel.style.display = 'none';
        elements.comparePanel.style.display = 'none';
    }
}

function toggleJMESPathPanel() {
    const visible = elements.jmespathPanel.style.display !== 'none';
    if (visible) {
        elements.jmespathPanel.style.display = 'none';
    } else {
        elements.jmespathPanel.style.display = 'block';
        elements.jmespathQuery.focus();
        // Close other panels to avoid overlap
        elements.searchPanel.style.display = 'none';
        elements.comparePanel.style.display = 'none';
    }
}

function toggleComparePanel() {
    const visible = elements.comparePanel.style.display !== 'none';
    if (visible) {
        elements.comparePanel.style.display = 'none';
    } else {
        elements.comparePanel.style.display = 'block';
        elements.compareJson1.focus();
        // Close other panels to avoid overlap
        elements.searchPanel.style.display = 'none';
        elements.jmespathPanel.style.display = 'none';
    }
}

// Clear node selection and hide actions bar
function clearNodeSelection() {
    if (state.selectedNode) {
        state.selectedNode.classList.remove('selected');
        state.selectedNode = null;
    }
    state.selectedNodePath = '';
    state.selectedNodeValue = null;
    elements.nodeActionsBar.style.display = 'none';
    elements.selectedNodePath.textContent = '';
}

// Copy selected node value
function copySelectedNode() {
    if (!state.selectedNodeValue) {
        showToast('No node selected', 'warning');
        return;
    }
    const text = JSON.stringify(state.selectedNodeValue, null, 2);
    navigator.clipboard.writeText(text).then(() => {
        showToast('Node copied to clipboard!', 'success');
    }).catch(() => {
        showToast('Failed to copy', 'error');
    });
}

// Filter by selected node's key
function filterBySelectedNode() {
    if (!state.selectedNodePath) {
        showToast('No node selected', 'warning');
        return;
    }
    // Extract the last key from the path
    const parts = state.selectedNodePath.split('.');
    const key = parts[parts.length - 1];
    
    if (state.parsedJson) {
        const filtered = extractValuesByKey(state.parsedJson, key);
        state.filteredJson = filtered;
        elements.outputEditor.value = JSON.stringify(filtered, null, 2);
        elements.treeView.innerHTML = '';
        renderTreeView(filtered, elements.treeView);
        showToast(`Filtered ${filtered.length} values for key "${key}"`, 'success');
    }
}

// Edit selected node value (opens a prompt for simple editing)
function editSelectedNode() {
    if (!state.selectedNodeValue) {
        showToast('No node selected', 'warning');
        return;
    }
    
    const currentValue = JSON.stringify(state.selectedNodeValue, null, 2);
    const modal = document.createElement('div');
    modal.className = 'modal';
    modal.style.display = 'block';
    modal.innerHTML = `
        <div class="modal-content" style="max-width: 600px;">
            <div class="modal-header">
                <h3>Edit Node Value</h3>
                <button class="btn btn-icon" id="closeEditModal">×</button>
            </div>
            <div class="modal-body">
                <textarea id="editNodeTextarea" style="width:100%;height:300px;font-family:var(--font-mono);font-size:14px;" spellcheck="false">${escapeHtml(currentValue)}</textarea>
            </div>
            <div class="modal-footer">
                <button class="btn" id="cancelEditBtn">Cancel</button>
                <button class="btn btn-primary" id="saveEditBtn">Save Changes</button>
            </div>
        </div>
    `;
    document.body.appendChild(modal);
    
    // Wire up buttons
    setTimeout(() => {
        const textarea = document.getElementById('editNodeTextarea');
        const closeBtn = document.getElementById('closeEditModal');
        const cancelBtn = document.getElementById('cancelEditBtn');
        const saveBtn = document.getElementById('saveEditBtn');
        
        closeBtn.addEventListener('click', () => modal.remove());
        cancelBtn.addEventListener('click', () => modal.remove());
        saveBtn.addEventListener('click', () => {
            try {
                const newValue = JSON.parse(textarea.value);
                // Update the tree view with new value
                state.selectedNodeValue = newValue;
                
                // Re-render tree with updated data
                if (state.isTreeView) {
                    renderTreeView(state.parsedJson, elements.treeView);
                } else {
                    elements.outputEditor.value = JSON.stringify(state.parsedJson, null, 2);
                }
                
                modal.remove();
                showToast('Node updated successfully!', 'success');
            } catch (e) {
                showToast('Invalid JSON: ' + e.message, 'error');
            }
        });
    }, 50);
}

function escapeHtml(str) {
    const div = document.createElement('div');
    div.textContent = str;
    return div.innerHTML;
}

// JMESPath Query Engine (Simplified Implementation)
function evaluateJMESPath(data, query) {
    try {
        if (!query || query.trim() === '') return data;
        const q = query.trim();
        
        // Handle *.property pattern
        if (q.startsWith('*.')) {
            const prop = q.substring(2);
            if (Array.isArray(data)) {
                return data.map(item => item && typeof item === 'object' ? item[prop] : undefined).filter(v => v !== undefined);
            }
            if (data && typeof data === 'object') {
                return Object.values(data).map(item => item && typeof item === 'object' ? item[prop] : undefined).filter(v => v !== undefined);
            }
        }
        
        // Handle [?condition].property pattern
        const filterMatch = q.match(/^\[\?([^\]]+)\]\.(.+)$/);
        if (filterMatch) {
            const condition = filterMatch[1];
            const prop = filterMatch[2];
            if (!Array.isArray(data)) return [];
            
            return data.filter(item => {
                if (!item || typeof item !== 'object') return false;
                const condMatch = condition.match(/([a-zA-Z_$][\w$]*)\s*(==|!=|>|<|>=|<=)\s*(?:`([^`]*)`|'([^']*)'|"([^"]*)"|(\d+\.?\d*))/);
                if (condMatch) {
                    const field = condMatch[1];
                    const op = condMatch[2];
                    let value = condMatch[3] || condMatch[4] || condMatch[5] || condMatch[6];
                    const itemVal = item[field];
                    
                    if (op === '==') {
                        if (value === 'true') return itemVal === true;
                        if (value === 'false') return itemVal === false;
                        const numVal = parseFloat(value);
                        if (!isNaN(numVal)) return itemVal == numVal;
                        return String(itemVal) === value || itemVal == value;
                    }
                    if (op === '!=') {
                        if (value === 'true') return itemVal !== true;
                        if (value === 'false') return itemVal !== false;
                        return String(itemVal) !== value && itemVal != value;
                    }
                    const numValue = parseFloat(value);
                    if (typeof itemVal === 'number') {
                        if (op === '>') return itemVal > numValue;
                        if (op === '<') return itemVal < numValue;
                        if (op === '>=') return itemVal >= numValue;
                        if (op === '<=') return itemVal <= numValue;
                    }
                }
                return false;
            }).map(item => item[prop]).filter(v => v !== undefined);
        }
        
        // Handle simple filter [?condition]
        const simpleFilterMatch = q.match(/^\[\?([^\]]+)\]$/);
        if (simpleFilterMatch) {
            const condition = simpleFilterMatch[1];
            if (!Array.isArray(data)) return [];
            
            return data.filter(item => {
                if (!item || typeof item !== 'object') return false;
                const condMatch = condition.match(/([a-zA-Z_$][\w$]*)\s*(==|!=)\s*(?:`([^`]*)`|'([^']*)'|"([^"]*)")/);
                if (condMatch) {
                    const field = condMatch[1];
                    const op = condMatch[2];
                    const value = condMatch[3] || condMatch[4] || condMatch[5];
                    const itemVal = item[field];
                    if (op === '==') return String(itemVal) === value || itemVal == value || (value === 'true' && itemVal === true);
                    if (op === '!=') return String(itemVal) !== value || itemVal != value;
                }
                return false;
            });
        }
        
        // Handle sort_by(@, &property)
        const sortByMatch = q.match(/^sort_by\(@,\s*&([a-zA-Z_$][\w$]*)\)$/);
        if (sortByMatch) {
            const prop = sortByMatch[1];
            if (!Array.isArray(data)) return data;
            return [...data].sort((a, b) => {
                const aVal = a && a[prop];
                const bVal = b && b[prop];
                if (typeof aVal === 'number' && typeof bVal === 'number') return aVal - bVal;
                return String(aVal || '').localeCompare(String(bVal || ''));
            });
        }
        
        // Handle reverse(@)
        if (q === 'reverse(@)' && Array.isArray(data)) {
            return [...data].reverse();
        }
        
        // Handle length(@)
        if (q === 'length(@)') {
            if (Array.isArray(data)) return data.length;
            if (data && typeof data === 'object') return Object.keys(data).length;
            return 0;
        }
        
        // Handle .property pattern
        if (q.startsWith('.')) {
            const prop = q.substring(1);
            if (Array.isArray(data)) {
                return data.map(item => item && typeof item === 'object' ? item[prop] : undefined).filter(v => v !== undefined);
            }
            return data && typeof data === 'object' ? data[prop] : undefined;
        }
        
        // Handle direct property access
        if (/^[a-zA-Z_$][\w$]*$/.test(q)) {
            if (Array.isArray(data)) {
                return data.map(item => item && typeof item === 'object' ? item[q] : undefined).filter(v => v !== undefined);
            }
            return data && typeof data === 'object' ? data[q] : undefined;
        }
        
        return data;
    } catch (e) {
        throw new Error('JMESPath error: ' + e.message);
    }
}

function filterByKey(data, key) {
    const results = [];
    function search(obj) {
        if (obj && typeof obj === 'object') {
            if (Array.isArray(obj)) {
                obj.forEach(search);
            } else {
                if (key in obj) results.push(obj[key]);
                Object.values(obj).forEach(search);
            }
        }
    }
    search(data);
    return results;
}

// Extract values by key - alias for filterByKey used in node actions
function extractValuesByKey(data, key) {
    return filterByKey(data, key);
}

function runJMESPathQuery() {
    const query = elements.jmespathQuery.value.trim();
    const inputJson = elements.inputEditor.value.trim();
    
    if (!inputJson) {
        showToast('Please enter JSON first', 'warning');
        return;
    }
    
    const result = validateJSON(inputJson);
    if (!result.valid) {
        showToast('Invalid JSON in input', 'error');
        return;
    }
    
    try {
        const output = evaluateJMESPath(result.data, query);
        elements.jmespathResults.innerHTML = '<pre class="jmespath-output">' + JSON.stringify(output, null, 2) + '</pre>';
        showToast('Query executed!', 'success');
    } catch (e) {
        elements.jmespathResults.innerHTML = '<div class="toast error">Error: ' + e.message + '</div>';
        showToast('Query failed', 'error');
    }
}

function applyKeyFilter() {
    const key = elements.filterKey.value.trim();
    const inputJson = elements.inputEditor.value.trim();
    
    if (!key) {
        showToast('Please enter a key name', 'warning');
        return;
    }
    
    if (!inputJson) {
        showToast('Please enter JSON first', 'warning');
        return;
    }
    
    const result = validateJSON(inputJson);
    if (!result.valid) {
        showToast('Invalid JSON in input', 'error');
        return;
    }
    
    try {
        const output = filterByKey(result.data, key);
        elements.jmespathResults.innerHTML = '<h4>Found ' + output.length + ' match(es) for key "' + key + '":</h4><pre class="jmespath-output">' + JSON.stringify(output, null, 2) + '</pre>';
        showToast('Found ' + output.length + ' match(es)', 'success');
    } catch (e) {
        elements.jmespathResults.innerHTML = '<div class="toast error">Error: ' + e.message + '</div>';
        showToast('Filter failed', 'error');
    }
}

// Compare
function compareJSON(json1, json2) {
    try {
        const obj1 = typeof json1 === 'string' ? JSON.parse(json1) : json1;
        const obj2 = typeof json2 === 'string' ? JSON.parse(json2) : json2;
        const results = [];
        
        function getType(val) {
            if (val === null) return 'null';
            if (Array.isArray(val)) return 'array';
            return typeof val;
        }
        
        function compare(v1, v2, path = '') {
            const t1 = getType(v1), t2 = getType(v2);
            
            if (t1 !== t2) {
                results.push({ path: path || '(root)', type: 'changed', old: v1, new: v2 });
                return;
            }
            
            if (t1 === 'object') {
                const k1 = Object.keys(v1), k2 = Object.keys(v2);
                k1.forEach(k => { if (!k2.includes(k)) results.push({ path: path ? `${path}.${k}` : k, type: 'removed', value: v1[k] }); });
                k2.forEach(k => { if (!k1.includes(k)) results.push({ path: path ? `${path}.${k}` : k, type: 'added', value: v2[k] }); });
                k1.forEach(k => { if (k2.includes(k)) compare(v1[k], v2[k], path ? `${path}.${k}` : k); });
            } else if (t1 === 'array') {
                const len = Math.max(v1.length, v2.length);
                for (let i = 0; i < len; i++) {
                    if (i >= v1.length) results.push({ path: `${path}[${i}]`, type: 'added', value: v2[i] });
                    else if (i >= v2.length) results.push({ path: `${path}[${i}]`, type: 'removed', value: v1[i] });
                    else compare(v1[i], v2[i], `${path}[${i}]`);
                }
            } else if (v1 !== v2) {
                results.push({ path: path || '(root)', type: 'changed', old: v1, new: v2 });
            }
        }
        
        compare(obj1, obj2);
        return results;
    } catch (e) {
        return [{ error: e.message }];
    }
}

function displayCompareResults(results) {
    if (results.some(r => r.error)) {
        elements.compareResults.innerHTML = `<div class="toast error">Error: ${results[0].error}</div>`;
        return;
    }
    if (results.length === 0) {
        elements.compareResults.innerHTML = '<div class="toast success">Documents are identical</div>';
        return;
    }
    
    let html = `<strong>${results.length} difference(s):</strong><br>`;
    results.forEach(r => {
        const icon = r.type === 'added' ? '+' : r.type === 'removed' ? '-' : '•';
        const cls = r.type === 'added' ? 'diff-added' : r.type === 'removed' ? 'diff-removed' : 'diff-changed';
        html += `<div class="${cls}">${icon} <strong>${r.path}</strong>: `;
        if (r.type === 'removed') html += JSON.stringify(r.value);
        else if (r.type === 'added') html += JSON.stringify(r.value);
        else html += `<span class="diff-removed">${JSON.stringify(r.old)}</span> → <span class="diff-added">${JSON.stringify(r.new)}</span>`;
        html += '</div>';
    });
    elements.compareResults.innerHTML = html;
}

// Conversions
function jsonToCSV(data) {
    if (!Array.isArray(data)) data = [data];
    if (data.length === 0) return '';
    const headers = Object.keys(data[0]);
    const rows = [headers.join(',')];
    data.forEach(row => {
        rows.push(headers.map(h => {
            const v = row[h];
            return typeof v === 'object' ? JSON.stringify(v) : `"${String(v).replace(/"/g, '""')}"`;
        }).join(','));
    });
    return rows.join('\n');
}

function jsonToXML(data, root = 'root') {
    function convert(obj, name) {
        if (obj === null) return `<${name}>null</${name}>`;
        if (typeof obj !== 'object') return `<${name}>${escapeXml(String(obj))}</${name}>`;
        if (Array.isArray(obj)) return obj.map(i => convert(i, name)).join('');
        let xml = `<${name}>`;
        Object.entries(obj).forEach(([k, v]) => xml += convert(v, k));
        return xml + `</${name}>`;
    }
    function escapeXml(s) {
        return s.replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
    }
    return '<?xml version="1.0"?>\n' + convert(data, root);
}

function jsonToYAML(data, indent = 0) {
    const sp = '  '.repeat(indent);
    if (data === null) return 'null';
    if (typeof data === 'boolean' || typeof data === 'number') return String(data);
    if (typeof data === 'string') return data.includes('\n') ? `|\n${sp}  ${data.split('\n').join('\n'+sp+'  ')}` : `"${data}"`;
    if (Array.isArray(data)) {
        if (data.length === 0) return '[]';
        return data.map(i => `\n${sp}- ${jsonToYAML(i, indent+1).trimStart()}`).join('');
    }
    if (typeof data === 'object') {
        const keys = Object.keys(data);
        if (keys.length === 0) return '{}';
        return keys.map(k => `\n${sp}${k}: ${jsonToYAML(data[k], indent+1).trimStart()}`).join('');
    }
    return String(data);
}

function showConvertModal(format) {
    const input = elements.outputEditor.value || elements.inputEditor.value;
    if (!input) { showToast('No JSON to convert', 'warning'); return; }
    
    const result = validateJSON(input);
    if (!result.valid) { showToast('Invalid JSON', 'error'); return; }
    
    let converted, title;
    try {
        switch (format) {
            case 'csv': converted = jsonToCSV(result.data); title = 'CSV'; break;
            case 'xml': converted = jsonToXML(result.data); title = 'XML'; break;
            case 'yaml': converted = jsonToYAML(result.data); title = 'YAML'; break;
        }
        elements.convertModalTitle.textContent = title + ' Output';
        elements.convertOutput.textContent = converted;
        elements.convertModal.style.display = 'flex';
        elements.convertModal.dataset.format = format;
    } catch (e) {
        showToast('Conversion error: ' + e.message, 'error');
    }
}

// File Operations
function downloadFile(content, filename, mime = 'application/json') {
    const blob = new Blob([content], { type: mime });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url; a.download = filename;
    document.body.appendChild(a); a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
}

function handleFileUpload(file) {
    if (!file.name.endsWith('.json')) { showToast('Please select a .json file', 'warning'); return; }
    const reader = new FileReader();
    reader.onload = e => {
        elements.inputEditor.value = e.target.result;
        updateStats(); syncLineNumbers();
        showToast(`Loaded ${file.name}`, 'success');
    };
    reader.readAsText(file);
}

async function copyToClipboard(text) {
    try {
        await navigator.clipboard.writeText(text);
        showToast('Copied!', 'success');
    } catch (e) {
        const ta = document.createElement('textarea');
        ta.value = text; document.body.appendChild(ta);
        ta.select(); document.execCommand('copy');
        document.body.removeChild(ta);
        showToast('Copied!', 'success');
    }
}

// Theme
function toggleTheme() {
    state.theme = state.theme === 'light' ? 'dark' : 'light';
    document.documentElement.setAttribute('data-theme', state.theme);
    localStorage.setItem('jsonToolsTheme', state.theme);
    document.querySelector('.icon-sun').style.display = state.theme === 'dark' ? 'none' : 'block';
    document.querySelector('.icon-moon').style.display = state.theme === 'dark' ? 'block' : 'none';
}

function loadTheme() {
    const saved = localStorage.getItem('jsonToolsTheme') || 'light';
    state.theme = saved;
    document.documentElement.setAttribute('data-theme', saved);
    if (saved === 'dark') {
        document.querySelector('.icon-sun').style.display = 'none';
        document.querySelector('.icon-moon').style.display = 'block';
    }
}

// Panel Resizing
function initResizer() {
    let resizing = false;
    elements.resizer.addEventListener('mousedown', e => {
        resizing = true;
        elements.resizer.classList.add('resizing');
        document.body.style.cursor = 'col-resize';
        e.preventDefault();
    });
    document.addEventListener('mousemove', e => {
        if (!resizing) return;
        const pct = ((e.clientX - elements.leftPanel.getBoundingClientRect().left) / elements.leftPanel.parentElement.offsetWidth) * 100;
        if (pct > 20 && pct < 80) {
            elements.leftPanel.style.flex = `0 0 ${pct}%`;
            elements.rightPanel.style.flex = `0 0 ${100-pct}%`;
        }
    });
    document.addEventListener('mouseup', () => {
        resizing = false;
        elements.resizer.classList.remove('resizing');
        document.body.style.cursor = '';
    });
}

// Event Listeners
function initEventListeners() {
    elements.inputEditor.addEventListener('input', () => {
        updateStats(); syncLineNumbers();
        clearTimeout(state.validateTimeout);
        state.validateTimeout = setTimeout(() => {
            if (elements.inputEditor.value.trim()) {
                const r = validateJSON(elements.inputEditor.value);
                setValidationStatus(r.valid, r.error);
            }
        }, 300);
    });
    
    elements.inputEditor.addEventListener('scroll', () => elements.inputLineNumbers.scrollTop = elements.inputEditor.scrollTop);
    elements.outputEditor.addEventListener('scroll', () => elements.outputLineNumbers.scrollTop = elements.outputEditor.scrollTop);
    
    elements.formatBtn.addEventListener('click', () => formatJSON(state.indentSize));
    elements.minifyBtn.addEventListener('click', minifyJSON);
    elements.validateBtn.addEventListener('click', () => {
        const r = validateJSON(elements.inputEditor.value);
        setValidationStatus(r.valid, r.error);
        showToast(r.valid ? 'Valid JSON!' : 'Invalid: ' + r.error, r.valid ? 'success' : 'error');
    });
    elements.fixBtn.addEventListener('click', fixJSON);
    elements.treeViewBtn.addEventListener('click', toggleTreeView);
    elements.compareBtn.addEventListener('click', toggleComparePanel);
    elements.searchBtn.addEventListener('click', toggleSearchPanel);
    
    elements.downloadBtn.addEventListener('click', () => {
        const c = elements.outputEditor.value || elements.inputEditor.value;
        if (c) { downloadFile(c, 'formatted.json'); showToast('Downloaded', 'success'); }
        else showToast('Nothing to download', 'warning');
    });
    
    elements.copyBtn.addEventListener('click', () => {
        const c = elements.outputEditor.value || elements.inputEditor.value;
        if (c) copyToClipboard(c);
        else showToast('Nothing to copy', 'warning');
    });
    
    elements.clearInputBtn.addEventListener('click', () => {
        elements.inputEditor.value = '';
        elements.outputEditor.value = '';
        state.parsedJson = null;
        setValidationStatus(false);
        updateStats(); syncLineNumbers();
        showToast('Cleared', 'info');
    });
    
    elements.expandAllBtn.addEventListener('click', expandAllTreeNodes);
    elements.collapseAllBtn.addEventListener('click', collapseAllTreeNodes);
    elements.themeToggle.addEventListener('click', toggleTheme);
    
    // Node actions bar
    elements.copyNodeBtn.addEventListener('click', copySelectedNode);
    elements.filterByNodeBtn.addEventListener('click', filterBySelectedNode);
    elements.editNodeBtn.addEventListener('click', editSelectedNode);
    elements.clearSelectionBtn.addEventListener('click', clearNodeSelection);
    
    elements.searchInput.addEventListener('input', e => searchJSON(e.target.value));
    elements.searchNextBtn.addEventListener('click', () => goToSearchMatch(state.currentSearchIndex + 1));
    elements.searchPrevBtn.addEventListener('click', () => goToSearchMatch(state.currentSearchIndex - 1));
    elements.closeSearchBtn.addEventListener('click', () => {
        elements.searchPanel.style.display = 'none';
        elements.searchInput.value = '';
        searchJSON('');
    });

    // Replace functionality
    elements.replaceBtn.addEventListener('click', replaceCurrentMatch);
    elements.replaceAllBtn.addEventListener('click', replaceAllMatches);
    
    // JMESPath panel
    elements.jmespathBtn.addEventListener('click', toggleJMESPathPanel);
    elements.runJmespathBtn.addEventListener('click', runJMESPathQuery);
    elements.applyFilterBtn.addEventListener('click', applyKeyFilter);
    elements.closeJmespathBtn.addEventListener('click', () => elements.jmespathPanel.style.display = 'none');
    
    // Example tags for JMESPath
    document.querySelectorAll('.example-tag').forEach(tag => {
        tag.addEventListener('click', () => {
            elements.jmespathQuery.value = tag.dataset.query;
            runJMESPathQuery();
        });
    });

    
    elements.doCompareBtn.addEventListener('click', () => {
        if (!elements.compareJson1.value || !elements.compareJson2.value) {
            showToast('Enter both JSON documents', 'warning'); return;
        }
        displayCompareResults(compareJSON(elements.compareJson1.value, elements.compareJson2.value));
    });
    elements.closeCompareBtn.addEventListener('click', () => elements.comparePanel.style.display = 'none');
    
    elements.convertBtn.addEventListener('click', e => { e.stopPropagation(); elements.convertDropdown.classList.toggle('show'); });
    elements.convertDropdown.querySelectorAll('button').forEach(btn => {
        btn.addEventListener('click', e => {
            showConvertModal(e.target.dataset.format);
            elements.convertDropdown.classList.remove('show');
        });
    });
    document.addEventListener('click', () => elements.convertDropdown.classList.remove('show'));
    
    elements.fileInput.addEventListener('change', e => { if (e.target.files.length) handleFileUpload(e.target.files[0]); });
    
    document.addEventListener('dragover', e => { e.preventDefault(); document.body.style.opacity = '0.7'; });
    document.addEventListener('dragleave', () => document.body.style.opacity = '1');
    document.addEventListener('drop', e => {
        e.preventDefault(); document.body.style.opacity = '1';
        if (e.dataTransfer.files.length) handleFileUpload(e.dataTransfer.files[0]);
    });
    
    elements.closeConvertModal.addEventListener('click', () => elements.convertModal.style.display = 'none');
    elements.copyConvertBtn.addEventListener('click', () => copyToClipboard(elements.convertOutput.textContent));
    elements.downloadConvertBtn.addEventListener('click', () => {
        const fmt = elements.convertModal.dataset.format || 'txt';
        downloadFile(elements.convertOutput.textContent, `converted.${fmt === 'yaml' ? 'yml' : fmt}`);
    });
    
    elements.indentSelect.addEventListener('change', e => {
        state.indentSize = e.target.value;
        localStorage.setItem('jsonToolsIndent', state.indentSize);
    });
    
    window.addEventListener('click', e => { if (e.target === elements.convertModal) elements.convertModal.style.display = 'none'; });
}

// Keyboard Shortcuts
function initKeyboardShortcuts() {
    document.addEventListener('keydown', e => {
        if (e.ctrlKey && e.key === 'Enter') { e.preventDefault(); formatJSON(state.indentSize); }
        if (e.ctrlKey && e.shiftKey && e.key === 'M') { e.preventDefault(); minifyJSON(); }
        if (e.ctrlKey && e.key === 'f') { e.preventDefault(); toggleSearchPanel(); }
        if (e.ctrlKey && e.key === 'c' && document.activeElement !== elements.inputEditor) {
            const c = elements.outputEditor.value;
            if (c) { e.preventDefault(); copyToClipboard(c); }
        }
        if (e.key === 'Escape') {
            elements.searchPanel.style.display = 'none';
            elements.comparePanel.style.display = 'none';
            elements.convertModal.style.display = 'none';
        }
    });
}

// Initialization
function loadSampleData() {
    const sample = {
        "name": "JSON Tools Demo",
        "version": "1.0.0",
        "features": ["Format", "Minify", "Validate", "Tree View", "Compare", "Convert"],
        "settings": { "theme": "auto", "indentSize": 2, "preserveUnicode": true },
        "author": { "name": "JSON Tools", "email": null, "active": true },
        "stats": { "downloads": 0, "rating": 5.0 }
    };
    elements.inputEditor.value = JSON.stringify(sample, null, 2);
    formatJSON(2);
}

function init() {
    initElements();
    loadTheme();
    state.indentSize = localStorage.getItem('jsonToolsIndent') || '2';
    elements.indentSelect.value = state.indentSize;
    
    initResizer();
    initEventListeners();
    initKeyboardShortcuts();
    loadSampleData();
    updateStats();
    syncLineNumbers();
    setStatus('Ready - Drop a JSON file or paste JSON to start');
}

if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
} else {
    init();
}
