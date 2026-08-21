import {
  DEFAULT_MAX_BYTES,
  DEFAULT_MAX_LINES,
  truncateTail,
  type ExtensionAPI,
} from "@earendil-works/pi-coding-agent";
import { resolve } from "node:path";
import { Type } from "typebox";

const prohibitedCommand = /(^|[\s;&|()])(?:git|hub|gh|pi|claude)(?=$|[\s;&|()])/i;
const destructiveCommand = /(^|[\s;&|()])(?:rm|rmdir|mv|chmod|chown)(?=$|[\s;&|()])/i;
const gitPath = /(^|[\\/])\.git(?:[\\/]|$)/i;

function parseNonEmptyStringArray(rawValue: string | undefined, variableName: string): string[] {
  if (!rawValue) throw new Error(`${variableName} must be a JSON array`);
  const parsedValue: unknown = JSON.parse(rawValue);
  if (!Array.isArray(parsedValue) || parsedValue.length === 0 || parsedValue.some((value) => typeof value !== "string" || !value.trim())) {
    throw new Error(`${variableName} must be a non-empty JSON array of non-empty strings`);
  }
  return parsedValue;
}

function validateChecks(checks: string[]): string[] {
  for (const check of checks) {
    if (prohibitedCommand.test(check) || destructiveCommand.test(check) || gitPath.test(check)) {
      throw new Error(`Unsafe approved check: ${check}`);
    }
  }
  return checks;
}

function resolveApprovedFiles(paths: string[]): Set<string> {
  return new Set(paths.map((path) => {
    if (gitPath.test(path)) throw new Error(`Unsafe approved file path: ${path}`);
    return resolve(process.cwd(), path);
  }));
}

function truncateOutput(output: string) {
  return truncateTail(output, { maxLines: DEFAULT_MAX_LINES, maxBytes: DEFAULT_MAX_BYTES }).content;
}

export default function (pi: ExtensionAPI) {
  const checks = validateChecks(parseNonEmptyStringArray(process.env.PI_DEVELOP_CHECKS_JSON, "PI_DEVELOP_CHECKS_JSON"));
  const approvedFiles = resolveApprovedFiles(parseNonEmptyStringArray(process.env.PI_DEVELOP_FILES_JSON, "PI_DEVELOP_FILES_JSON"));

  pi.registerTool({
    name: "run_check",
    label: "Run approved check",
    description: `Run one Sol-approved check by index. You cannot provide shell text.\n${checks.map((check, index) => `${index}: ${check}`).join("\n")}`,
    parameters: Type.Object({
      index: Type.Integer({ minimum: 0, maximum: checks.length - 1 }),
    }),
    async execute(_toolCallId, params, signal) {
      const command = checks[params.index];
      const result = await pi.exec("bash", ["-lc", command], { signal });
      const output = truncateOutput(`${result.stdout}${result.stderr}`);
      const details = { command, output, exitCode: result.code, killed: result.killed };

      if (result.code !== 0) {
        throw new Error(`Approved check failed: ${command}\nExit code: ${result.code}\n${output}`);
      }
      return { content: [{ type: "text", text: output }], details };
    },
  });

  pi.on("tool_call", (event) => {
    if (event.toolName === "write" || event.toolName === "edit") {
      const targetPath = event.input.path as string;
      if (gitPath.test(targetPath)) return { block: true, reason: "Terra coder cannot access .git" };
      if (!approvedFiles.has(resolve(process.cwd(), targetPath))) {
        return { block: true, reason: "Terra coder can modify only Sol-approved files" };
      }
    }
  });
}
