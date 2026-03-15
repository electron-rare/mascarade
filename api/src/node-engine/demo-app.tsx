/**
 * Demo app for NodeEditor component
 *
 * Simple standalone demo to verify ReactFlow canvas renders correctly.
 * This is a temporary file for subtask-3-1 verification.
 */

import { createRoot } from 'react-dom/client';
import { NodeEditor } from './components/NodeEditor';

const root = document.getElementById('root');
if (root) {
  createRoot(root).render(<NodeEditor />);
} else {
  console.error('Root element not found');
}
