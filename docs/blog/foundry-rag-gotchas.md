# Deploying a RAG pipeline on Microsoft Foundry: the gotchas nobody warns you about

*Draft blog post — keep the specifics, swap in your environment details before publishing.*

We stood up a production-style RAG pipeline on Microsoft Foundry: Azure OpenAI
(`gpt-4.1-mini` + `text-embedding-3-large`), Azure AI Search (free tier),
`azure-ai-evaluation`, and a one-command deployment with Bicep + `az`. The happy
path is a 20-minute job. Ours took a day, and almost none of the time went into
the pipeline itself — it went into deployment, lifecycle, and tooling gotchas.

Here is every wall we hit, with the fix.

---

## 1. The model version you picked is probably retired by now

**Symptom**
```
InvalidTemplateDeployment ... ServiceModelDeprecated:
The model 'Format:OpenAI,Name:gpt-4o-mini,Version:2024-07-18' has been
deprecated since 03/31/2026 00:00:00.
```

**Cause** Azure OpenAI retires *specific versions* on a schedule, and Standard
deployments of `gpt-4o-mini 2024-07-18` were retired for new deployments in
2026. Hardcoding a version in IaC is a time bomb.

**Fix** Discover what is actually deployable in your region at deploy time and
try candidates in order. `az cognitiveservices model list` is the source of truth:

```powershell
$models = az cognitiveservices model list --location $Location -o json | ConvertFrom-Json
foreach ($p in @("gpt-4.1-mini","gpt-5-mini","gpt-5.4-mini")) {
    $m = $models | Where-Object { $_.model.name -eq $p } | Select-Object -First 1
    if ($m) { ...deploy $m.model.name $m.model.version...; break }
}
```

**Lesson** Never pin a model *version* in Bicep unless you are prepared to
maintain it. Treat the version as data, not a constant.

---

## 2. `gpt-5`-class models reject the `Standard` SKU

**Symptom**
```
InvalidResourceProperties: The specified SKU 'Standard' of account deployment
is not supported by the model 'gpt-5-mini' version '2025-08-07'.
```

**Cause** Reasoning-class models are only offered on `GlobalStandard` (and other
global/data-zone SKUs), not regional `Standard`.

**Fix** Choose the SKU per model family:

```powershell
function Get-ChatSku($name) {
    if ($name -like 'gpt-5*' -or $name -like 'o1*' -or $name -like 'o3*' -or $name -like 'o4*') {
        return 'GlobalStandard'
    }
    return 'Standard'
}
```

**Lesson** "Deploy a model" is a three-variable problem: model, **version**, and
**SKU**. Getting two of three right still fails.

---

## 3. A deleted resource group does not free the account name

**Symptom**
```
FlagMustBeSetForRestore: An existing resource with ID '.../accounts/ragpipeline-xxxx'
has been soft-deleted. ... please purge it first.
```

**Cause** Deleting a Foundry/AI Services account *soft-deletes* it. The name
stays reserved.

**Fix** Purge the soft-deleted account before recreating, or use a fresh name:

```powershell
az cognitiveservices account purge --name <account> --resource-group <rg> --location <region>
# or list them all:
az cognitiveservices account list-deleted -o table
```

**Lesson** Teardown is not a clean slate. If you must reuse names, purge first.

---

## 4. Retrying a failed deployment can deadlock the parent resource

**Symptom**
```
RequestConflict: Another operation is being performed on the parent resource
'.../accounts/ragpipeline-xxxx'. Please try again later.
```

**Cause** Our first template bundled the account **and** the model deployments.
Every retry re-submitted the whole template, which re-touched the account while
the previous operation was still finalizing — a self-inflicted race.

**Fix** Split the deploy into two phases:

1. Deploy the account + Search **once** (idempotent).
2. Create each **model deployment separately** via the CLI, so retries only
   touch the deployment resource, never the account.

```powershell
az cognitiveservices account deployment create `
  --name $account --resource-group $rg `
  --deployment-name gpt-4-1-mini `
  --model-name gpt-4.1-mini --model-version 2025-04-14 --model-format OpenAI `
  --sku-name Standard --sku-capacity 50
```

**Lesson** Retried operations must be as *narrow* as possible. Never make a
retry re-apply unrelated resources.

---

## 5. Windows PowerShell's `Set-Content -Encoding UTF8` adds a BOM

**Symptom** `python-dotenv` reads the first key as `\ufeffAZURE_OPENAI_ENDPOINT`,
so your app reports a *missing* env var even though the file looks perfect.

**Cause** In Windows PowerShell 5.1, `-Encoding UTF8` writes a UTF-8 **BOM**.

**Fix** Write `.env` explicitly without a BOM:

```powershell
[System.IO.File]::WriteAllText($path, $content, (New-Object System.Text.UTF8Encoding($false)))
```

**Lesson** "It's just a text file" is how half a day disappears. Check for a BOM
whenever a `.env` or config file "exists but isn't read."

---

## 6. `Write-Host ("=" * 64) -ForegroundColor ...` silently mis-parses

**Symptom** Your banner prints the literal text `- ForegroundColor DarkGray`.

**Cause** When the first argument is a parenthesized expression, PowerShell can
treat the following `-Parameter` as a positional string.

**Fix** Assign to a variable first:

```powershell
$Bar = "=" * 64
Write-Host $Bar -ForegroundColor DarkGray
```

**Lesson** PowerShell argument mode is subtle after parenthesized expressions.
When in doubt, bind parameters with a variable or put the parameter first.

---

## 7. A PowerShell function returns *all* its output — including your exit code test

**Symptom** A verification script always reported `FAIL` even though the command
succeeded.

**Cause** The helper returned the command's stdout *and* `$LASTEXITCODE`:

```powershell
function Invoke-Rag($args) {
    & python -m ragpipeline @args
    return $LASTEXITCODE   # but stdout was emitted too!
}
if ((Invoke-Rag @("ingest")) -ne 0) { ... }   # array "ingested 3 chunks",0 -> truthy
```

The function returned `@("ingested 3 chunks", 0)`, and `-ne 0` was truthy.

**Fix** Capture output explicitly, then return only the code:

```powershell
$out = & python -m ragpipeline @args 2>&1
$code = $LASTEXITCODE
$out | ForEach-Object { Write-Host $_ }
return $code
```

**Lesson** In PowerShell, unwritten output is the return value. Capture it or
you will "fail" on success.

---

## 8. `$ErrorActionPreference = "Stop"` turns native stderr into a crash

**Symptom** Probing `py -3.12 --version` aborted the whole script with
`NativeCommandError: No suitable Python runtime found`.

**Cause** With `Stop`, a native command writing to stderr becomes terminating.

**Fix** Probe defensively and let the fallback run:

```powershell
$probe = (& py $v --version 2>&1) -join " "
if ($LASTEXITCODE -eq 0) { ... }
```

**Lesson** `$ErrorActionPreference = "Stop"` is great for cmdlets and hostile to
native tools. Handle native exit codes explicitly.

---

## 9. Capacity is bounded by *quota*, and Standard quota may be near-zero

**Symptom** `ask` works, but the evaluation harness retries for minutes and dies:
```
RateLimitError: ... exceeded token rate limit
```
even after you set deployment `capacity` to 50.

**Cause** Two compounding things. First, an Azure OpenAI Standard deployment's
`capacity` is measured in thousands of tokens per minute, so `capacity: 1` is
~1K TPM. Second — and this is the sneaky one — your *deployment* capacity is
capped by your *subscription* quota. We set `capacity 50` on a `Standard`
deployment and still throttled, because the subscription's real-time
`Standard.gpt4.1-mini` quota was effectively the bottleneck. The accurate quota
view showed generous `GlobalStandard` capacity available:

```powershell
az cognitiveservices usage list --location eastus `
  --query "[?contains(name.value,'Standard')].{name:name.value, limit:limit, used:currentValue}" -o table
```

**Fix** Deploy the chat model on `GlobalStandard` (draws from the global pool),
and/or point the evaluators at a separate, higher-quota deployment:

```powershell
az cognitiveservices account deployment delete ... --deployment-name gpt-4-1-mini
az cognitiveservices account deployment create ... --sku-name GlobalStandard --sku-capacity 50
```
```python
# evaluators can use a different, higher-quota deployment than the app
model_config = {
    "azure_endpoint": os.environ["AZURE_OPENAI_ENDPOINT"],
    "api_key": os.environ["AZURE_OPENAI_API_KEY"],
    "azure_deployment": os.environ.get("EVAL_DEPLOYMENT_NAME", MODEL_DEPLOYMENT_NAME),
}
```

**Lesson** `capacity` is a request, not a guarantee — the subscription quota
decides. Separate _serving_ traffic from _evaluation_ traffic, and prefer
`GlobalStandard` when regional `Standard` quota is thin. Also note the quota
table truncates wide names in `-o table`; query it with `--query`, not
`Select-String`.

---

## 10. You forgot FinOps until the bill arrived

**Symptom** Untagged resources, no idea what belongs to whom.

**Fix** Tag everything at deploy time and give dev resources an expiry:

```bicep
var commonTags = {
  project: projectName
  environment: environment
  owner: owner
  costCenter: costCenter
  managedBy: 'bicep'
  workload: 'ai-103-portfolio'
  dataClassification: 'public'
  expiresOn: expiresOn   // drives an automated cleanup job
}
```

Then:
- `infra/budget.ps1` — subscription budget + portal alert thresholds.
- `infra/cleanup-expired.ps1` — deletes groups whose `expiresOn` has passed.
- Report by tag in Cost Management (`group by: tag > project`).

**Lesson** Cost attribution is a day-one concern, not a cleanup task.

---

## 11. Azure AI Search lets you *add* fields, never *remove* them

**Symptom** After changing the index schema (adding `parent_id`, `section`,
`parent_content` for parent-child chunking), `create_or_update_index` failed:
```
OperationNotAllowed: Existing field(s) 'chunk_index' cannot be deleted.
```

**Cause** Azure AI Search indexes are not fully mutable. You can add fields,
but you cannot drop or change existing ones in place.

**Fix** Reset (delete + recreate) the index when the schema changes, and make
that a first-class command:

```python
if getattr(args, "recreate", False):
    reset_index()
else:
    create_index()
```

```powershell
python -m ragpipeline ingest --recreate
```

**Lesson** Treat the index schema as a versioned artifact. Schema changes are
migrations, and a migration you can't roll back needs a rebuild path.

## The pre-flight checklist we now use

- [ ] Model **name + version + SKU** discovered from the region, not hardcoded
- [ ] Account/Search deployed **once**; model deployments applied separately
- [ ] Auth: keys for local dev, managed identity + RBAC for prod
- [ ] `.env` written **without BOM**
- [ ] `capacity` sized for the heaviest consumer (usually the evaluators)
- [ ] Evaluators can target a **separate deployment**
- [ ] Every resource tagged; dev resources carry `expiresOn`
- [ ] Budget + alert configured
- [ ] `teardown` script and `cleanup-expired` scheduled
- [ ] Idempotent provisioning: re-running never breaks a healthy stack

## Closing

None of these are RAG problems. They are **platform-operations** problems —
lifecycle, SKUs, IaC idempotency, Windows tooling, and cost. That is exactly the
gap between "I wrote a RAG demo" and "I can operate this in Azure." If you are
preparing for AI-103 or building a portfolio, the gotchas are the portfolio.
