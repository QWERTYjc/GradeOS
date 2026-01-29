const fs = require('fs');
const path = require('path');

const filePath = path.join(process.cwd(), 'src/store/consoleStore.ts');
const content = fs.readFileSync(filePath, 'utf8');
const lines = content.split('\n');

const newLines = lines.map(line => {
    // Fix line 1707: unterminated string (missing backtick and/or corrupt quote)
    if (line.includes('批改完成:') && line.includes('的分，题目:')) {
        // Matches specific Chinese pattern seen in error?
        // Error view: `页面 ${pageIndex} 批改完成: ${score}/${maxScore} 分，题目: ${questionNumbers?.join(', ') || '未识?}`,
        return `        \`页面 \${pageIndex} 批改完成: \${score}/\${maxScore} 分，题目: \${questionNumbers?.join(', ') || 'Unknown'}\`,`;
    }
    // Try simpler match if exact Chinese chars are risky
    if (line.includes('${pageIndex}') && line.includes('${score}/${maxScore}') && line.includes('questionNumbers')) {
        return `        \`Page \${pageIndex} graded: \${score}/\${maxScore}, Questions: \${questionNumbers?.join(', ') || 'Unknown'}\`,`;
    }
    return line;
});

fs.writeFileSync(filePath, newLines.join('\n'), 'utf8');
console.log('Fixed consoleStore.ts part 5');
