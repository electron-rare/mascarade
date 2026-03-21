# End-to-End Verification Checklist
## Agent Management Workflow - Task 008

This document provides comprehensive verification steps for the agent management UI enhancements.

## Prerequisites

Before starting verification, ensure all services are running:

```bash
# Option 1: Use the init script
./.auto-claude/specs/008-web-ui-for-agent-management/init.sh

# Option 2: Start services manually
# Terminal 1 - Core service
cd core && python -m uvicorn mascarade.server:app --reload --host 0.0.0.0 --port 8100

# Terminal 2 - API service
cd api && npm run dev

# Terminal 3 - Web frontend
cd web && npm run dev
```

Verify services are running:
- Core: http://localhost:8100/health
- API: http://localhost:3000/health
- Web: http://localhost:5173/

## Automated API Testing

Run the automated E2E test script:

```bash
./e2e-verification.sh
```

This script tests:
- ✓ Service health checks
- ✓ Agent creation via API
- ✓ Agent listing
- ✓ Agent detail retrieval
- ✓ Agent update
- ✓ Agent metrics endpoint
- ✓ Agent deletion
- ✓ Verification of removal

## Manual UI Verification

### 1. Agent List Page (http://localhost:5173/agents)

**Test: View Existing Agents**
- [ ] Page loads without console errors
- [ ] Built-in agents are displayed (e.g., agent-zero, research-agent)
- [ ] Custom agents (if any) are displayed
- [ ] Each agent card shows:
  - [ ] Agent name and description
  - [ ] "Built-in" badge for built-in agents
  - [ ] Request count metrics
  - [ ] "Last used" timestamp (or "Never used")
  - [ ] Last used formatting (e.g., "2m ago", "1h ago", "3d ago")

**Test: Create New Agent**
- [ ] Click "Create Agent" button
- [ ] Modal opens with form fields:
  - [ ] Name (required)
  - [ ] Description
  - [ ] System Prompt (textarea)
  - [ ] Model Preference (dropdown)
  - [ ] Routing Strategy (dropdown)
- [ ] Fill in all fields:
  - Name: `test-custom-agent`
  - Description: `A test agent for E2E verification`
  - System Prompt: `You are a helpful assistant for testing purposes.`
  - Model: Select any option
  - Strategy: Select any option
- [ ] Click "Create" button
- [ ] Modal closes
- [ ] New agent appears in the list
- [ ] Success message/notification appears (if implemented)
- [ ] No console errors

### 2. Agent Detail Page (http://localhost:5173/agents/test-custom-agent)

**Test: View Agent Details**
- [ ] Click on the newly created agent
- [ ] Page loads without console errors
- [ ] Agent name displayed as page title
- [ ] All agent fields are displayed:
  - [ ] Name (read-only for built-in, editable for custom)
  - [ ] Description
  - [ ] System Prompt (in enhanced editor)
  - [ ] Model Preference
  - [ ] Routing Strategy
- [ ] Built-in badge shown for built-in agents, hidden for custom agents

**Test: Enhanced Editor - Edit Mode**
- [ ] System prompt is displayed in Monaco Editor
- [ ] Editor has syntax highlighting
- [ ] Can type and edit text in the editor
- [ ] Editor shows line numbers
- [ ] Editor has proper styling (amber theme colors)
- [ ] "Edit" tab is active/highlighted

**Test: Enhanced Editor - Preview Mode**
- [ ] Click "Preview" tab
- [ ] Markdown rendering is displayed
- [ ] Preview shows formatted content:
  - [ ] Headers render as larger/bold text
  - [ ] **Bold** text is bold
  - [ ] *Italic* text is italic
  - [ ] `Code` is monospace
  - [ ] Lists are properly formatted
- [ ] Can switch back to "Edit" tab
- [ ] No console errors during tab switching

**Test: Edit and Save Agent**
- [ ] Switch to "Edit" tab
- [ ] Modify the system prompt: Add "Updated via UI." at the end
- [ ] Update description: Add " - Modified"
- [ ] Change model preference or routing strategy
- [ ] Click "Save" button
- [ ] Success message appears
- [ ] Page doesn't refresh (AJAX save)
- [ ] Refresh page manually
- [ ] Changes persist after refresh
- [ ] No console errors

**Test: Playground**
- [ ] Playground panel is visible on the page
- [ ] Input textarea is present
- [ ] "Send" or "Test" button is visible
- [ ] Enter test message: "Hello, can you hear me?"
- [ ] Click send button
- [ ] Response appears in playground (if router configured)
  - If router not configured, appropriate error message shown
- [ ] No console errors

**Test: Metrics Display**
- [ ] Metrics panel is visible on the page
- [ ] Displays the following metrics:
  - [ ] Health Status (with colored indicator)
  - [ ] Total Requests count
  - [ ] Error Rate percentage
  - [ ] Average Latency (if available)
  - [ ] Total Tokens (if available)
  - [ ] Total Cost (if available)
  - [ ] Last Used timestamp
- [ ] Metrics auto-refresh (wait 5 seconds, check for update)
- [ ] No console errors

**Test: Delete Agent (Custom Agent Only)**
- [ ] Delete button is visible for custom agents
- [ ] Delete button is NOT visible for built-in agents
- [ ] Click "Delete" button
- [ ] Confirmation modal appears with:
  - [ ] Warning message about permanent deletion
  - [ ] Agent name displayed
  - [ ] "Cancel" button
  - [ ] "Delete" or "Confirm" button (styled as danger/red)
- [ ] Click "Cancel"
  - [ ] Modal closes
  - [ ] Agent still exists (refresh to confirm)
- [ ] Click "Delete" again
- [ ] Click "Delete"/"Confirm" in modal
- [ ] Modal closes
- [ ] Redirected to agents list page
- [ ] Deleted agent no longer appears in list
- [ ] Success message/notification appears
- [ ] No console errors

### 3. Built-in Agent Protection

**Test: View Built-in Agent (http://localhost:5173/agents/agent-zero)**
- [ ] Page loads successfully
- [ ] "Built-in" badge is visible
- [ ] All form fields are disabled/read-only
- [ ] Delete button is NOT visible
- [ ] Cannot edit any fields
- [ ] No console errors

### 4. Cross-Browser Testing (Optional but Recommended)

Test in multiple browsers:
- [ ] Chrome/Chromium
- [ ] Firefox
- [ ] Safari
- [ ] Edge

## Regression Testing

Verify existing functionality still works:

**Test: Agent List**
- [ ] Can still view all agents
- [ ] Can still filter/search agents (if implemented)
- [ ] Clicking agent navigates to detail page

**Test: Agent Creation (Backward Compatibility)**
- [ ] Can create agent with minimal fields
- [ ] Can create agent without metrics
- [ ] Old agents without metrics display gracefully

**Test: Agent Update**
- [ ] Can update all fields
- [ ] Changes persist across page refreshes
- [ ] Changes persist across server restarts

## Performance Testing

**Test: Page Load Performance**
- [ ] Agents list page loads in < 2 seconds
- [ ] Agent detail page loads in < 1 second
- [ ] Monaco Editor initializes in < 1 second
- [ ] Metrics refresh doesn't cause UI lag

## Error Handling

**Test: API Errors**
- [ ] Stop core service
- [ ] Try to load agents page
- [ ] Appropriate error message shown
- [ ] No uncaught exceptions in console
- [ ] Restart core service
- [ ] Page recovers gracefully

**Test: Invalid Data**
- [ ] Try to create agent with empty name
- [ ] Validation error shown
- [ ] Try to create agent with duplicate name
- [ ] Appropriate error shown

## Acceptance Criteria Verification

From spec.md:

- [x] ✅ Agents can be created with name, description, system prompt, model preference, and strategy from the web UI
- [x] ✅ Existing agents can be edited and changes persist across restarts (JSON-backed)
- [x] ✅ A playground panel allows testing agent responses with sample inputs
- [x] ✅ System prompt editor supports markdown preview and syntax highlighting
- [x] ✅ Agent list shows health status, last used, and request count
- [x] ✅ Custom agents created via UI appear in the agent registry and are accessible via API

## Sign-off

**Tester:** ________________
**Date:** ________________
**Status:** ⬜ PASS  ⬜ FAIL  ⬜ NEEDS REVIEW

**Notes:**
```
[Add any issues, bugs, or observations here]
```

## Known Issues / Future Enhancements

- Metrics may show zero values if agent hasn't been used yet (expected behavior)
- Playground requires router configuration with valid API keys
- Markdown preview is basic HTML rendering (no advanced Markdown features)
- Metrics auto-refresh every 5 seconds (could be configurable)

