const fs = require('fs');
const path = require('path');

const filePath = path.join(process.cwd(), 'src/store/consoleStore.ts');
const content = fs.readFileSync(filePath, 'utf8');

// Global replacement of untyped event handler callbacks
const newContent = content.replace(/, \(data\) => {/g, ', (data: any) => {');

fs.writeFileSync(filePath, newContent, 'utf8');
console.log('Fixed consoleStore.ts part 9 (types)');
