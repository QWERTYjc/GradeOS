const fs = require('fs');
const path = require('path');

const filePath = path.join(process.cwd(), 'src/store/consoleStore.ts');
const content = fs.readFileSync(filePath, 'utf8');
const lines = content.split('\n');

const newLines = lines.map(line => {
    // Fix malformed comments closing with ?/ instead of */
    if (line.includes('/**') && (line.includes('?/') || line.trim().endsWith('/'))) {
        // Try to reconstruct the comment or just clean it to /** Comment */
        if (line.includes('页面范围')) return '    /** 页面范围（显示用） */';
        if (line.includes('第一次批改记录')) return '    /** 第一次批改记录（逻辑复核前的原始结果） */';
        if (line.includes('第一次批改总分')) return '    /** 第一次批改总分 */';
        if (line.includes('第一次批改满分') || line.includes('第一次批改满')) return '    /** 第一次批改满分 */';
        if (line.includes('逻辑复核时间')) return '    /** 逻辑复核时间 */';
        if (line.includes('页面列表')) return '    /** 页面列表 */';
        if (line.includes('起始')) return '    /** 起始页 */';
        if (line.includes('结束')) return '    /** 结束页 */';
        if (line.includes('置信')) return '    /** 置信度 */';
        if (line.includes('是否需要人工')) return '    /** 是否需要人工确认 */';

        // Generic fix if we missed specific matching
        return line.replace('?/', '*/').replace(/([^/*])\/$/, '$1*/');
    }
    return line;
});

fs.writeFileSync(filePath, newLines.join('\n'), 'utf8');
console.log('Fixed consoleStore.ts part 6');
