import { useEffect, useState } from "react";
import {
  ExternalLink,
  GitBranch,
  GitPullRequest,
  KeyRound,
  Lock,
  ShieldCheck,
} from "lucide-react";
import { Btn, Dialog, DialogActions } from "./Dialog";
import { FIELD } from "../lib/ui";
import { secretSet, secretStatus } from "../lib/secrets";
import { openUrl } from "../lib/open";
import { openPr, planPr, type PrOpened, type PrPlan } from "../lib/pr";
import { toast } from "../lib/toast";
import { t as tr } from "../lib/i18n";

/**
 * 开 PR 的审批卡（v1.0）：推送之前把 仓库 / 分支 → 目标分支 / 标题 / 提交与改动文件 摆出来，用户确认才推送。
 * 没有授权时就地引导填 GitHub 令牌（最小权限说明 + 创建链接），存系统凭据库。
 */
export function PrDialog({
  open,
  onClose,
  runId,
  repo,
  onOpened,
}: {
  open: boolean;
  onClose: () => void;
  runId: string;
  repo?: string | null;
  onOpened?: (pr: PrOpened) => void;
}) {
  return (
    <Dialog
      open={open}
      onClose={onClose}
      title={tr("开 PR")}
      testId="pr-dialog"
      width={520}
    >
      {open && (
        <Body onClose={onClose} runId={runId} repo={repo} onOpened={onOpened} />
      )}
    </Dialog>
  );
}

function Body({
  onClose,
  runId,
  repo,
  onOpened,
}: {
  onClose: () => void;
  runId: string;
  repo?: string | null;
  onOpened?: (pr: PrOpened) => void;
}) {
  const [plan, setPlan] = useState<PrPlan | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [done, setDone] = useState<PrOpened | null>(null);
  const [token, setToken] = useState("");
  const [canStore, setCanStore] = useState(false);
  const [nonce, setNonce] = useState(0);
  useEffect(() => {
    let live = true;
    void planPr(runId, repo).then((r) => {
      if (!live) return;
      setErr(r.ok ? null : r.error);
      if (r.ok) setPlan(r.data);
    });
    void secretStatus("github").then(
      (s) => live && setCanStore(s !== "unsupported"),
    );
    return () => {
      live = false;
    };
  }, [runId, repo, nonce]);

  const saveToken = async () => {
    const v = token.trim();
    if (!v || busy) return;
    setBusy(true);
    try {
      await secretSet(v, "github");
      setToken("");
      toast(tr("已存入系统凭据库"));
      setNonce((n) => n + 1);
    } catch (e) {
      setErr(String(e instanceof Error ? e.message : e));
    } finally {
      setBusy(false);
    }
  };
  const confirm = async () => {
    if (!plan || busy) return;
    setBusy(true);
    setErr(null);
    const r = await openPr(runId, repo, plan.base);
    setBusy(false);
    if (!r.ok) return setErr(r.error);
    setDone(r.data);
    onOpened?.(r.data);
  };

  if (done) {
    return (
      <>
        <p className="text-[13.5px] text-ink-soft" data-testid="pr-opened">
          {done.created
            ? tr("已开 PR #{0}", String(done.number))
            : tr("这个分支已有 PR #{0}", String(done.number))}{" "}
          · {done.repo}
        </p>
        <button
          type="button"
          onClick={() => void openUrl(done.url)}
          className="mt-2 inline-flex items-center gap-1.5 font-mono text-[12.5px] text-amber-ink hover:underline"
          data-testid="pr-url"
        >
          <ExternalLink size={12} strokeWidth={1.8} />
          {done.url}
        </button>
        <DialogActions>
          <Btn kind="solid" onClick={onClose}>
            {tr("好")}
          </Btn>
        </DialogActions>
      </>
    );
  }
  if (!plan) {
    return (
      <>
        <p className="text-[13px] text-sepia" data-testid="pr-plan-state">
          {err ?? tr("正在读取分支和远端…")}
        </p>
        <DialogActions>
          <Btn onClick={onClose}>{tr("关闭")}</Btn>
        </DialogActions>
      </>
    );
  }
  return (
    <>
      <dl
        className="grid grid-cols-[88px_1fr] gap-x-3 gap-y-2 text-[13px]"
        data-testid="pr-plan"
      >
        <dt className="text-sepia-muted">{tr("仓库")}</dt>
        <dd className="font-mono text-ink" data-testid="pr-repo">
          {plan.full_name}
        </dd>
        <dt className="text-sepia-muted">{tr("分支")}</dt>
        <dd
          className="flex items-center gap-1.5 font-mono text-[12.5px] text-ink"
          data-testid="pr-branch"
        >
          <GitBranch size={12} strokeWidth={1.7} className="text-sepia" />
          {plan.head} → {plan.base}
        </dd>
        <dt className="text-sepia-muted">{tr("标题")}</dt>
        <dd className="text-ink" data-testid="pr-title">
          {plan.title}
        </dd>
        <dt className="text-sepia-muted">{tr("改动")}</dt>
        <dd className="text-ink-soft">
          {tr(
            "{0} 个提交 · {1} 个文件",
            String(plan.commits),
            String(plan.files.length),
          )}
          <span className="ml-1.5 font-mono text-[11.5px] text-sepia-muted">
            {plan.files.slice(0, 4).join(" ")}
          </span>
        </dd>
      </dl>
      {plan.existing_url && (
        <p className="mt-3 text-[12px] text-sepia">
          {tr("之前已开过：")}
          <button
            type="button"
            className="font-mono text-amber-ink hover:underline"
            onClick={() => void openUrl(plan.existing_url!)}
          >
            {plan.existing_url}
          </button>
        </p>
      )}
      <p className="mt-3 flex items-start gap-1.5 text-[11.5px] leading-relaxed text-sepia-muted">
        <ShieldCheck size={12} strokeWidth={1.8} className="mt-0.5 shrink-0" />
        {tr(
          "确认后会把分支推送到 GitHub 并创建 PR（对外可见）；不会强推、不会合并。",
        )}
      </p>
      {plan.auth === null && (
        <div
          className="mt-3 rounded-xl border border-border-soft bg-parchment/60 p-3"
          data-testid="pr-need-token"
        >
          <p
            className="text-[12.5px] leading-relaxed text-ink-soft"
            data-allow-wrap
          >
            {tr("还没有 GitHub 授权。")} {plan.guidance}
          </p>
          <button
            type="button"
            onClick={() => void openUrl(plan.token_url)}
            className="mt-2 inline-flex items-center gap-1.5 text-[12px] text-amber-ink hover:underline"
          >
            <ExternalLink size={12} strokeWidth={1.8} />
            {tr("去 GitHub 创建令牌")}
          </button>
          {canStore ? (
            <div className="mt-2 flex gap-2">
              <input
                type="password"
                autoComplete="off"
                spellCheck={false}
                value={token}
                data-testid="pr-token-input"
                onChange={(e) => setToken(e.target.value)}
                onKeyDown={(e) =>
                  e.key === "Enter" &&
                  !e.nativeEvent.isComposing &&
                  void saveToken()
                }
                placeholder="github_pat_…"
                className={FIELD}
                aria-label={tr("GitHub 令牌")}
              />
              <Btn
                onClick={() => void saveToken()}
                disabled={!token.trim() || busy}
              >
                <KeyRound size={12} strokeWidth={1.8} /> {tr("保存")}
              </Btn>
            </div>
          ) : (
            <p className="mt-2 text-[11.5px] text-sepia-muted">
              {tr(
                "浏览器预览无法访问系统凭据库：请在桌面应用里填写，或在本机运行 gh auth login。",
              )}
            </p>
          )}
          <p className="mt-2 flex items-center gap-1.5 text-[11px] text-sepia-muted">
            <Lock size={10} strokeWidth={2} />{" "}
            {tr("令牌只存进系统凭据库，不会写进文件或日志。")}
          </p>
        </div>
      )}
      {plan.auth && (
        <p
          className="mt-2 text-[11.5px] text-sepia-muted"
          data-testid="pr-auth"
        >
          {plan.auth === "token"
            ? tr("使用凭据库里的 GitHub 令牌")
            : tr("使用本机已登录的 gh")}
        </p>
      )}
      {err && (
        <p className="mt-2 text-[12px] text-rose-ink" data-testid="pr-error">
          {err}
        </p>
      )}
      <DialogActions>
        <Btn onClick={onClose}>{tr("取消")}</Btn>
        <Btn
          kind="solid"
          onClick={() => void confirm()}
          disabled={!plan.auth || busy}
          testId="pr-confirm"
        >
          <GitPullRequest size={12} strokeWidth={1.8} />{" "}
          {busy ? tr("正在推送…") : tr("推送并开 PR")}
        </Btn>
      </DialogActions>
    </>
  );
}
