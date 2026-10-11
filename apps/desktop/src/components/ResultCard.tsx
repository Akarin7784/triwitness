import { useState } from "react";
import {
  ChevronDown,
  ClipboardCopy,
  ExternalLink,
  FolderOpen,
  GitBranch,
  GitPullRequest,
  ScrollText,
} from "lucide-react";
import clsx from "clsx";
import type { ResultMsg } from "../bridge/protocol";
import { costTitle, fmtCny } from "../lib/money";
import { prSummary } from "../bridge/liveTask";
import { t } from "../lib/i18n";
import { openUrl, revealPath } from "../lib/open";
import { PrDialog } from "./PrDialog";
import type { PrOpened } from "../lib/pr";
import { inTauri } from "../lib/appWindow";
import { toast } from "../lib/toast";

const VERDICT: Record<string, { label: string; cls: string }> = {
  pass: { label: t("复验通过"), cls: "bg-sage/14 text-sage" },
  fail: { label: t("复验未过"), cls: "bg-rose-ink/12 text-rose-ink" },
  inconclusive: { label: t("证据不足"), cls: "bg-amber/14 text-amber-ink" },
};

const STATUS: Record<string, string> = {
  done: t("已完成"),
  failed: t("未完成"),
  stuck: t("卡住"),
  budget_exceeded: t("触及安全上限"),
  cancelled: t("已停止"),
  error: t("出错"),
};

/**
 * 任务结尾的结论卡（UI-10，最小版）：裁决 · 风险 · PR 说明摘要；完整证据页后续做。
 * 核心先只生成本地分支 tw/<run_id> + PR 说明（pr.md）；v1.0 起可以「开 PR」：审批卡上看清
 * 仓库 / 分支 / 标题后确认，才推送分支并在 GitHub 上创建 PR（PrDialog）。
 */
export function ResultCard({ result }: { result: ResultMsg }) {
  const [open, setOpen] = useState(false);
  const [prOpen, setPrOpen] = useState(false);
  const [pr, setPr] = useState<PrOpened | null>(null);
  const canPr = result.status === "done" && !!result.branch && !!result.run_id;
  const v = result.verdict ? VERDICT[result.verdict] : null;
  const lines = prSummary(result.pr_md, open ? 200 : 6);
  return (
    <article
      data-testid="result-card"
      className="paper-card fade-in mr-auto w-full max-w-[720px] rounded-2xl px-5 py-4"
    >
      <div className="flex flex-wrap items-center gap-2">
        <span
          className={clsx(
            "inline-flex items-center rounded-full px-3 py-0.5 font-serif text-[15px] font-medium",
            v?.cls ?? "bg-border-soft text-sepia",
          )}
        >
          {v?.label ?? STATUS[result.status] ?? result.status}
        </span>
        {result.risk_level && (
          <span className="chip">{t("风险 {0}", result.risk_level)}</span>
        )}
        {result.clean_env === "verified" && (
          <span className="chip">{t("干净环境")}</span>
        )}
        <span
          data-testid="result-cost"
          className="chip ml-auto tabular-nums"
          title={costTitle(result)}
        >
          {t("¥{0} · {1} 步", fmtCny(result.cost_cny), result.steps)}
        </span>
      </div>
      {result.summary && (
        <p className="selectable mt-3 text-[14px] leading-[1.8] text-ink-soft">
          {result.summary}
        </p>
      )}
      {result.reason && !result.summary && (
        <p className="selectable mt-3 text-[13px] leading-[1.8] text-sepia">
          {result.reason}
        </p>
      )}
      {lines.length > 0 && (
        <div className="mt-3 border-t border-border-soft pt-3">
          <div className="mb-1.5 flex items-center gap-1.5 text-[11px] tracking-[0.12em] text-sepia-muted">
            <ScrollText size={12} strokeWidth={1.6} />
            pr.md
          </div>
          <pre className="selectable whitespace-pre-wrap font-mono text-[12px] leading-relaxed text-ink-soft">
            {lines.join("\n")}
          </pre>
          <button
            type="button"
            onClick={() => setOpen((o) => !o)}
            className="mt-1 inline-flex items-center gap-1 text-[11.5px] text-sepia-muted transition-colors hover:text-amber-ink"
          >
            <ChevronDown
              size={12}
              className={clsx("transition-transform", open && "rotate-180")}
            />
            {open ? t("收起") : t("全文")}
          </button>
        </div>
      )}
      {(result.branch || result.pr_md) && (
        <div
          className="mt-3 border-t border-border-soft pt-3"
          data-testid="result-delivery"
        >
          <p className="text-[12px] leading-relaxed text-sepia">
            {pr
              ? t("已推送分支并开 PR #{0}。", String(pr.number))
              : t(
                  "已生成本地分支和 PR 说明；还没有推送。点「开 PR」先看审批卡，确认后才推送并在 GitHub 上创建 PR。",
                )}
          </p>
          {result.branch && (
            <p className="mt-1 inline-flex items-center gap-1 font-mono text-[11px] text-sepia-muted">
              <GitBranch size={11} strokeWidth={1.6} />
              {result.branch}
            </p>
          )}
          <div className="mt-2 flex flex-wrap gap-2">
            {canPr && !pr && (
              <button
                type="button"
                className="chip hover:text-amber-ink"
                data-testid="open-pr"
                onClick={() => setPrOpen(true)}
              >
                <GitPullRequest size={11} strokeWidth={1.7} />
                {t("开 PR")}
              </button>
            )}
            {pr && (
              <button
                type="button"
                className="chip text-sage hover:text-amber-ink"
                data-testid="pr-link"
                onClick={() => void openUrl(pr.url)}
              >
                <ExternalLink size={11} strokeWidth={1.7} />
                {t("PR #{0}", String(pr.number))}
              </button>
            )}
            {result.pr_md && (
              <button
                type="button"
                className="chip hover:text-amber-ink"
                data-testid="copy-pr-body"
                onClick={() => void copyPr(result.pr_md!)}
              >
                <ClipboardCopy size={11} strokeWidth={1.7} />
                {t("复制 PR 说明")}
              </button>
            )}
            {result.run_dir && inTauri && (
              <button
                type="button"
                className="chip hover:text-amber-ink"
                data-testid="open-run-dir"
                onClick={() => void openRunDir(result.run_dir!)}
              >
                <FolderOpen size={11} strokeWidth={1.7} />
                {t("打开运行目录")}
              </button>
            )}
          </div>
        </div>
      )}
      {canPr && (
        <PrDialog
          open={prOpen}
          onClose={() => setPrOpen(false)}
          runId={result.run_id!}
          repo={result.repo}
          onOpened={setPr}
        />
      )}
    </article>
  );
}

async function copyPr(md: string) {
  try {
    await navigator.clipboard.writeText(md);
    toast(t("已复制 PR 说明"));
  } catch {
    toast(t("复制失败"));
  }
}

async function openRunDir(dir: string) {
  if (!(await revealPath(dir))) toast(t("打不开运行目录"));
}
