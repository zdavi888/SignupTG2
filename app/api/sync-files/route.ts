import { NextResponse } from 'next/server';
import fs from 'fs';
import path from 'path';

function getFilesRecursively(dir: string, baseDir: string) {
  let results: any[] = [];
  const list = fs.readdirSync(dir);
  for (const file of list) {
    const filePath = path.join(dir, file);
    const stat = fs.statSync(filePath);
    if (stat && stat.isDirectory()) {
      if (file === '__pycache__' || file === '.venv' || file === 'node_modules' || file === '.git') continue;
      results.push({
        type: 'folder',
        name: file,
        path: path.relative(baseDir, filePath),
        children: getFilesRecursively(filePath, baseDir)
      });
    } else {
      if (file.endsWith('.pyc') || file.endsWith('.used.txt')) continue;
      const content = fs.readFileSync(filePath, 'utf-8');
      results.push({
        type: 'file',
        name: file,
        path: path.relative(baseDir, filePath),
        content
      });
    }
  }
  return results;
}

export async function GET() {
  try {
    const targetDir = path.join(process.cwd(), '自动注册TG/自动注册TG');
    const files = getFilesRecursively(targetDir, targetDir);
    return NextResponse.json({ files });
  } catch (error) {
    console.error("Error reading dir:", error);
    return NextResponse.json({ error: String(error) }, { status: 500 });
  }
}
