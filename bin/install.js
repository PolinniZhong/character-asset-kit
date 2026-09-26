#!/usr/bin/env node
'use strict';

/**
 * character-asset-kit installer
 * 把本 Skill 的 payload（SKILL.md + references + profiles + scripts + templates）
 * 复制到目标 Agent 的 skills 目录。零依赖，仅用 Node 内置模块。
 *
 * 用法：
 *   npx character-asset-kit install <target...> [--scope user|project] [--cwd <dir>]
 *   target: claude | codex | cursor | dsh | doubao | all
 * 示例：
 *   npx character-asset-kit install all
 *   npx character-asset-kit install claude codex
 *   npx character-asset-kit install claude --scope project
 */

const fs = require('fs');
const os = require('os');
const path = require('path');

const PKG_ROOT = path.resolve(__dirname, '..');
const SKILL_DIR_NAME = 'character-asset-kit';
const VERSION = require(path.join(PKG_ROOT, 'package.json')).version;

// 复制到目标 skills 目录的 payload（相对包根）
const PAYLOAD = [
  'SKILL.md',
  'skill.yaml',
  'references',
  'profiles',
  'scripts',
  'templates',
  'README.md',
  'LICENSE',
];

// 用户级：各 Agent skills 目录（相对 home）+ 用于探测该 Agent 是否已安装的 marker
const USER_TARGETS = {
  claude: { skillsDir: '.claude/skills', marker: '.claude' },
  codex: { skillsDir: '.codex/skills', marker: '.codex' },
  cursor: { skillsDir: '.cursor/skills', marker: '.cursor' },
  dsh: { skillsDir: '.agents/skills', marker: '.agents' },
};

// 项目级：各 Agent skills 目录（相对项目根）
const PROJECT_TARGETS = {
  claude: '.claude/skills',
  codex: '.codex/skills',
  cursor: '.cursor/skills',
  dsh: '.agents/skills',
};

// 豆包用户级 skills 目录（仅 macOS）
function doubaoSkillsDir() {
  if (process.platform !== 'darwin') return null;
  return path.join(
    os.homedir(),
    'Library', 'Application Support', 'Doubao', 'Default',
    '.doubao', 'agent_mode', 'workspace', '.user_skills'
  );
}

function parseArgs(argv) {
  const positionals = [];
  const opts = { scope: 'user', cwd: process.cwd(), help: false, version: false };
  for (let i = 0; i < argv.length; i++) {
    const a = argv[i];
    if (a === '--scope') {
      opts.scope = argv[++i];
    } else if (a.startsWith('--scope=')) {
      opts.scope = a.slice('--scope='.length);
    } else if (a === '--cwd') {
      opts.cwd = argv[++i];
    } else if (a.startsWith('--cwd=')) {
      opts.cwd = a.slice('--cwd='.length);
    } else if (a === '--help' || a === '-h') {
      opts.help = true;
    } else if (a === '--version' || a === '-v') {
      opts.version = true;
    } else if (a.startsWith('-')) {
      throw new Error(`未知选项：${a}`);
    } else {
      positionals.push(a);
    }
  }
  return { positionals, opts };
}

function printHelp() {
  console.log(`character-asset-kit v${VERSION} — 千面工坊·角色资产生产线安装器

用法：
  npx character-asset-kit install <target...> [选项]

目标 target（可多个）：
  claude   Claude Code（~/.claude/skills）
  codex    OpenAI Codex CLI（~/.codex/skills）
  cursor   Cursor（~/.cursor/skills）
  dsh      开放 Agent Skills 标准 / DSH（~/.agents/skills，Codex 也扫描此处）
  doubao   豆包（仅 macOS 用户级）
  all      安装到所有已检测到的 Agent（用户级按已存在的配置目录探测）

选项：
  --scope <user|project>   用户级（默认）或当前项目级
  --cwd <dir>              project 作用域的项目路径（默认当前目录）
  -h, --help               显示帮助
  -v, --version            显示版本

示例：
  npx character-asset-kit install all
  npx character-asset-kit install claude codex
  npx character-asset-kit install claude --scope project
`);
}

// 计算单个 target 的目标目录；返回 { dir, skip }
function resolveTarget(name, scope, cwd) {
  if (scope === 'project') {
    if (name === 'doubao') {
      return { skip: '豆包仅支持用户级（--scope user）' };
    }
    const rel = PROJECT_TARGETS[name];
    if (!rel) return { bad: true };
    return { dir: path.join(cwd, rel, SKILL_DIR_NAME) };
  }

  // user scope
  if (name === 'doubao') {
    const dir = doubaoSkillsDir();
    if (!dir) return { skip: '豆包目标仅支持 macOS' };
    return { dir: path.join(dir, SKILL_DIR_NAME) };
  }
  const t = USER_TARGETS[name];
  if (!t) return { bad: true };
  return { dir: path.join(os.homedir(), t.skillsDir, SKILL_DIR_NAME) };
}

// 展开 all：用户级只包含 marker 已存在的 Agent；项目级包含全部四个
function expandAll(scope, cwd) {
  if (scope === 'project') {
    return Object.keys(PROJECT_TARGETS);
  }
  const found = [];
  for (const [name, t] of Object.entries(USER_TARGETS)) {
    if (fs.existsSync(path.join(os.homedir(), t.marker))) found.push(name);
  }
  const dbDir = doubaoSkillsDir();
  if (dbDir && fs.existsSync(dbDir)) found.push('doubao');
  return found;
}

function copyPayload(destDir) {
  fs.mkdirSync(destDir, { recursive: true });
  let count = 0;
  for (const entry of PAYLOAD) {
    const src = path.join(PKG_ROOT, entry);
    if (!fs.existsSync(src)) continue;
    fs.cpSync(src, path.join(destDir, entry), { recursive: true, force: true });
    count++;
  }
  return count;
}

function main() {
  let parsed;
  try {
    parsed = parseArgs(process.argv.slice(2));
  } catch (e) {
    console.error(`错误：${e.message}\n`);
    printHelp();
    process.exit(2);
  }
  const { positionals, opts } = parsed;

  if (opts.help) { printHelp(); return; }
  if (opts.version) { console.log(VERSION); return; }

  const [command, ...requested] = positionals;
  if (!command) { printHelp(); return; }
  if (command !== 'install') {
    console.error(`错误：未知命令“${command}”，应为 install\n`);
    printHelp();
    process.exit(2);
  }
  if (requested.length === 0) {
    console.error('错误：install 需要至少一个目标（claude/codex/cursor/dsh/doubao/all）\n');
    printHelp();
    process.exit(2);
  }
  if (!['user', 'project'].includes(opts.scope)) {
    console.error(`错误：--scope 仅支持 user 或 project，收到“${opts.scope}”`);
    process.exit(2);
  }

  // 展开 all
  let names = requested;
  if (requested.includes('all')) {
    names = expandAll(opts.scope, opts.cwd);
    const explicit = requested.filter((n) => n !== 'all');
    names = [...new Set([...explicit, ...names])];
  }

  if (names.length === 0) {
    console.error(
      '未检测到任何已安装的 Agent。请先安装对应 Agent，或显式指定目标，例如：\n' +
      '  npx character-asset-kit install claude'
    );
    process.exit(1);
  }

  console.log(`千面工坊 v${VERSION} · 安装到 ${opts.scope === 'project' ? '项目' : '用户'}级\n`);

  const installed = [];
  const skipped = [];
  for (const name of names) {
    const r = resolveTarget(name, opts.scope, opts.cwd);
    if (r.bad) {
      console.error(`错误：未知目标“${name}”（可选 claude/codex/cursor/dsh/doubao/all）`);
      process.exit(2);
    }
    if (r.skip) {
      skipped.push(`${name}：${r.skip}`);
      continue;
    }
    try {
      copyPayload(r.dir);
      installed.push({ name, dir: r.dir });
    } catch (e) {
      console.error(`安装 ${name} 失败：${e.message}`);
      process.exit(1);
    }
  }

  for (const it of installed) {
    console.log(`  ✓ ${it.name.padEnd(7)} → ${it.dir}`);
  }
  for (const s of skipped) {
    console.log(`  · 跳过 ${s}`);
  }

  console.log(`\n已安装 ${installed.length} 个目标。若 Agent 正在运行，请重启或重新加载 skills 列表。`);
  console.log('然后对 Agent 说：“用千面工坊建一个新角色”。');
}

main();
