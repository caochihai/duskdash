const fs = require('fs');
const path = require('path');

const srcDir = path.join(__dirname, 'src');

const chatComponents = [
  'AIDisclaimer',
  'AgentTrace',
  'AssistantMessage',
  'AttachmentChip',
  'AttachmentPreview',
  'ChatComposer',
  'ChatWorkspace',
  'MarkdownContent',
  'MessageBlocks',
  'MessageList',
  'SHBAmbientBackground',
  'SecurityAlert',
  'SlashCommandPopup',
  'SourceDrawer',
  'SuggestedQuestions',
  'ThinkingIndicator',
  'UserMessage',
  'WelcomeState',
  'ProductRecommendationCard' // arguably chat or product feature
];

const customerComponents = [
  'CustomerProfileDrawer',
  'CustomerRecordGrid',
  'CustomerSummaryCard',
  'CustomerWorkspacePanel',
  'LoanApprovalCard',
  'LoanEstimateCard'
];

function ensureDir(dir) {
  if (!fs.existsSync(dir)) {
    fs.mkdirSync(dir, { recursive: true });
  }
}

const aiDir = path.join(srcDir, 'components', 'ai');
const chatDir = path.join(srcDir, 'features', 'chat', 'components');
const customerDir = path.join(srcDir, 'features', 'customer', 'components');

ensureDir(chatDir);
ensureDir(customerDir);

// 1. Move files
const movedMap = new Map(); // oldPath -> newPath
const importMap = new Map(); // oldImport -> newImport

// Helper to move component and its css module
function moveComponent(name, sourceDir, targetDir, newImportBase) {
  const exts = ['.tsx', '.ts', '.module.css'];
  exts.forEach(ext => {
    const oldFile = path.join(sourceDir, `${name}${ext}`);
    if (fs.existsSync(oldFile)) {
      const newFile = path.join(targetDir, `${name}${ext}`);
      fs.renameSync(oldFile, newFile);
      movedMap.set(oldFile, newFile);
      console.log(`Moved ${name}${ext}`);
    }
  });
  importMap.set(`@/components/ai/${name}`, `${newImportBase}/${name}`);
}

chatComponents.forEach(name => moveComponent(name, aiDir, chatDir, '@/features/chat/components'));
customerComponents.forEach(name => moveComponent(name, aiDir, customerDir, '@/features/customer/components'));

// Move ConversationSidebar from layout to chat
const layoutDir = path.join(srcDir, 'components', 'layout');
moveComponent('ConversationSidebar', layoutDir, chatDir, '@/features/chat/components');
importMap.set(`@/components/layout/ConversationSidebar`, `@/features/chat/components/ConversationSidebar`);

// 2. Update imports everywhere
function updateImportsInFile(filePath) {
  if (!filePath.endsWith('.tsx') && !filePath.endsWith('.ts')) return;
  let content = fs.readFileSync(filePath, 'utf8');
  let changed = false;
  
  for (const [oldImp, newImp] of importMap.entries()) {
    // Exact match for the import path
    const regex = new RegExp(`['"]${oldImp}['"]`, 'g');
    if (regex.test(content)) {
      content = content.replace(regex, `'${newImp}'`);
      changed = true;
    }
  }
  
  if (changed) {
    fs.writeFileSync(filePath, content, 'utf8');
    console.log(`Updated imports in ${path.relative(__dirname, filePath)}`);
  }
}

function walkDir(dir) {
  const files = fs.readdirSync(dir);
  for (const file of files) {
    const fullPath = path.join(dir, file);
    if (fs.statSync(fullPath).isDirectory()) {
      walkDir(fullPath);
    } else {
      updateImportsInFile(fullPath);
    }
  }
}

walkDir(srcDir);

// Delete the empty ai directory if it's empty
try {
  fs.rmdirSync(aiDir);
  console.log('Removed empty components/ai directory');
} catch (e) {
  console.log('Could not remove components/ai (might not be empty):', e.message);
}

console.log('Refactoring complete.');
