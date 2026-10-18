# -*- mode: Starlark -*-
# Tilt dashboard for the Seeker workspace.  Start it with:  mise run local:tilt:up
#
# Nothing here is deployed: every resource is a local command, so the dashboard is a live picture of
# the workspace.  Resources are grouped by label in the UI:
#
#   setup      uv sync of the whole workspace (everything else waits for it)
#   sdks/apps/services   one resource per package in the uv workspace, found by scripts/workspace_graph.py
#              (so `mise run sdk:new` adds a resource by itself).  Each one runs that package's tests,
#              waits for the packages it depends on, and re-runs when its own code OR the code of
#              anything it depends on changes, so editing seeker-sdk-core lights up every dependent.
#   scripts    tests of the repo's own tooling scripts (scripts/tests)
#   registry   the dependency graph and the plugins found through entry points
#   data       reports on data/videos_master.json; refreshed whenever the file changes
#   knowledge  the model tool queue, what each processing strategy has done, the evaluation comparison
#   methods    which method (youtube_api / ytdlp / youtube_transcript_api) local, act and gh use, with a button
#              to change local or act; the list refreshes by itself when fnox.local.toml or .vars changes
#   run        buttons (manual: press the "trigger" arrow) for the local update/rebuild/transcripts tasks
#   build      the separate seeker_* wheels
#   act / gh / docker   the same tasks as `mise run act:...` / `gh:...` / `docker:...`
#
# Only read-only or test resources run by themselves.  Anything that writes data, needs Docker or the
# network is manual.  Nothing here publishes or changes GitHub: `gh:videos:update`, `gh:videos:rebuild`
# (they really commit and open issues) and `gh:method:set` (it changes the repository variable the real
# workflows read) are deliberately not buttons; use the mise tasks or the TUI for those.

version_settings(constraint='>=0.33.0')
analytics_settings(enable=False)
update_settings(max_parallel_updates=4)
docker_prune_settings(disable=True)  # no images are built here; never let Tilt prune Docker
watch_settings(ignore=[
    '**/__pycache__', '**/*.pyc', '**/.pytest_cache', '.venv', '.act', 'dist', 'data/transcripts', 'logs',
])

config.define_string('video')  # `tilt up -- --video VIDEO_ID`: the video the transcripts compare button uses
config.define_string('limit')  # `tilt up -- --limit 10`: how many transcripts the download button fetches (default 5)
cfg = config.parse()

MASTER = 'data/videos_master.json'
PYTEST = 'uv run --no-sync pytest'
SEEKER = 'uv run --no-sync seeker'

# ---- the workspace -----------------------------------------------------------------------------

packages = decode_json(local('uv run --no-project python scripts/workspace_graph.py --json', quiet=True))['packages']
by_name = {p['name']: p for p in packages}  # dependencies come before dependents
pyprojects = ['pyproject.toml', 'uv.lock'] + [p['dir'] + '/pyproject.toml' for p in packages]
watch_file('scripts/workspace_graph.py')

local_resource(
    'setup',
    cmd='uv sync --all-packages',
    deps=pyprojects,
    labels=['setup'],
)

for p in packages:
    # Re-run when the package, or anything it depends on, changes.
    code = [p['dir'] + '/src', p['dir'] + '/tests', p['dir'] + '/pyproject.toml']
    code += [by_name[r]['dir'] + '/src' for r in p['requires']]
    if p['has_tests']:
        cmd = PYTEST + ' ' + p['dir']
    else:
        cmd = 'uv run --no-sync python -c "import %s; print(\'imports fine, no tests yet\')"' % p['module']
    local_resource(
        p['id'],
        cmd=cmd,
        deps=code,
        resource_deps=['setup'] + [by_name[d]['id'] for d in p['depends_on']],
        labels=[p['kind']],
        allow_parallel=True,
    )

# The repo's own tooling scripts (workspace graph, ...).
local_resource(
    'scripts',
    cmd=PYTEST + ' scripts',
    deps=['scripts', 'eval'],  # eval/questions are validated by scripts/tests
    resource_deps=['setup'],
    labels=['scripts'],
    allow_parallel=True,
)

# ---- registry ----------------------------------------------------------------------------------

local_resource(
    'workspace-graph',
    cmd='uv run --no-project python scripts/workspace_graph.py',
    deps=['scripts/workspace_graph.py'] + pyprojects,
    labels=['registry'],
)
local_resource(
    'plugins',
    cmd='uv sync --all-packages --quiet && %s plugins' % SEEKER,
    deps=pyprojects,
    resource_deps=['setup'],
    labels=['registry'],
)

# ---- data (read-only; refreshed when the master list changes) ------------------------------------

local_resource(
    'videos-report',
    cmd='%s videos manage report' % SEEKER,
    deps=[MASTER],
    resource_deps=['setup'],
    labels=['data'],
)
local_resource(
    'transcripts-stats',
    cmd='%s transcripts stats' % SEEKER,
    deps=[MASTER],
    resource_deps=['setup'],
    labels=['data'],
)

local_resource(
    'transcripts-missing',
    cmd='%s transcripts list-missing --limit 15' % SEEKER,
    deps=[MASTER],
    resource_deps=['setup'],
    labels=['data'],
)

# ---- knowledge (read-only views; they refresh while workers answer the queue) ------------------------

local_resource(
    'llm-queue',
    cmd='%s llm status' % SEEKER,   # requests waiting for a model (subagents now, Gemini later), cache per tool
    deps=['data/llm/queue'],
    resource_deps=['setup'],
    labels=['knowledge'],
)
local_resource(
    'knowledge-status',
    cmd='%s knowledge status' % SEEKER,
    deps=['data/knowledge'],
    resource_deps=['setup'],
    labels=['knowledge'],
)
local_resource(
    'eval-compare',
    cmd='%s eval compare' % SEEKER,   # the latest evaluation of every (processing, chat) pair
    deps=['data/eval/latest'],
    resource_deps=['setup'],
    labels=['knowledge'],
)

local_resource(
    'chat',
    serve_cmd='uv run --no-sync seeker-chat --headless',   # Chainlit; each user gives their own Gemini key
    labels=['knowledge'],
    auto_init=False,
    trigger_mode=TRIGGER_MODE_MANUAL,
    links=[link('http://localhost:8000', 'Chat')],
)

# ---- methods (read-only list; refreshed when a method is changed) -------------------------------------

local_resource(
    'methods',
    cmd='mise run all:method:show',  # local: fnox.local.toml, act: .vars, gh: repository variables (read only)
    deps=['fnox.local.toml', '.vars'],
    labels=['methods'],
)

def button(name, resource, text, argv, inputs=None, confirm=False, icon='settings'):
    """A button on a resource. Each input becomes an environment variable of the command (`inputs` is a list of
    (variable, label, choices)). Built from Tilt's own objects, so no extension has to be downloaded."""
    v1alpha1.ui_button(
        name=name,
        location=v1alpha1.ui_component_location(component_id=resource, component_type='resource'),
        text=text,
        icon_name=icon,
        requires_confirmation=confirm,
        inputs=[v1alpha1.ui_input_spec(name=var, label=label, choice=v1alpha1.ui_choice_input_spec(choices=choices))
                for (var, label, choices) in (inputs or [])],
    )
    v1alpha1.cmd(name=name + '-cmd', args=argv, start_on=v1alpha1.start_on_spec(ui_buttons=[name]))

# Only local and act: changing the gh variable would change the real daily workflow. The setting and the
# method are one choice, so a combination the script would refuse (like master-list = youtube_transcript_api)
# cannot be picked. A button's own output goes to the (Tiltfile) log, not to this resource; the list above
# refreshes by itself when the change is written, which is the confirmation.
METHOD_CHOICES = [
    'master-list = ytdlp', 'master-list = youtube_api', 'master-list = unset',
    'transcript = ytdlp', 'transcript = youtube_transcript_api', 'transcript = unset',
]
button(
    'set-method', 'methods', 'Set a method (local or act)',
    ['sh', '-c', 'set -- $CHOICE; scripts/method.sh "$PLACE" set "$1" "$3"'],
    inputs=[
        ('PLACE', 'Where', ['local', 'act']),
        ('CHOICE', 'Setting = method (unset: back to the default)', METHOD_CHOICES),
    ],
    confirm=True,
)

# ---- run (manual; these write data or use the network) -------------------------------------------

def manual(name, cmd, labels, **kwargs):
    local_resource(name, cmd=cmd, labels=labels, auto_init=False, trigger_mode=TRIGGER_MODE_MANUAL, **kwargs)

videos = read_json(MASTER, default={}).get('videos', [])
video = cfg.get('video', videos[0]['video_id'] if videos else '')

manual('videos-update', 'mise run local:videos:update', ['run'], resource_deps=['setup'])
manual('videos-rebuild', 'mise run local:videos:rebuild', ['run'], resource_deps=['setup'])
manual('transcripts-download',
       'mise run local:transcripts:manage -- download-missing --limit %s' % cfg.get('limit', '5'),
       ['run'], resource_deps=['setup'])  # the method comes from TRANSCRIPT_METHOD (see the methods resource)
if video:
    manual('transcripts-compare', 'mise run local:transcripts:compare -- %s' % video, ['run'], resource_deps=['setup'])

# ---- build ---------------------------------------------------------------------------------------

# Waits for every package's tests, so a red package blocks the build.
manual(
    'build-wheels',
    'mise run build:sdks && mise run build:apps',
    ['build'],
    resource_deps=[p['id'] for p in packages if p['kind'] in ('sdks', 'apps')],
)

# ---- act / gh / docker ---------------------------------------------------------------------------

manual('act-videos-update', 'mise run act:videos:update', ['act'])
manual('docker-diagnose', 'mise run docker:diagnose', ['docker'])

remote = str(local('git config --get remote.origin.url || true', quiet=True)).strip()
if remote.startswith('git@github.com:'):
    remote = 'https://github.com/' + remote[len('git@github.com:'):]
if remote.endswith('.git'):
    remote = remote[:-len('.git')]
manual(
    'gh-runs',
    'mise run gh:list',
    ['gh'],
    links=[link(remote + '/actions', 'GitHub Actions')] if remote.startswith('https://github.com/') else [],
)
