"""OpenClaw integration adapters for the monitor system."""
import os
import json
import subprocess
import time
import logging
import requests
from pathlib import Path
from typing import Any, Dict, List, Optional
from runtime.adapters.base import RuntimeAdapter, AdapterError
from .extras import ExtrasAdapter
from .agent import AgentAdapter
from runtime.adapters.memory import MemoryAdapter
import sqlite3
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

# Resolve openclaw binary location
OPENCLAW_BIN = os.getenv('OPENCLAW_BIN', '/Users/clawdbot/.nvm/versions/node/v22.22.0/bin/openclaw')

def _run_openclaw(cmd: List[str], **kwargs) -> subprocess.CompletedProcess:
    full_cmd = [OPENCLAW_BIN] + cmd[1:]
    return subprocess.run(full_cmd, **kwargs)

class EmailAdapter(RuntimeAdapter):
    def call(self, target: str, args: List[Any], context: Dict[str, Any]) -> Any:
        if target != 'G':
            raise AdapterError('email only supports G')
        try:
            result = _run_openclaw(
                ['openclaw', 'mail', 'check', '--unread', '--json'],
                capture_output=True, text=True, timeout=10
            )
            if result.returncode != 0:
                logger.warning(f'mail check failed: {result.stderr}')
                return []
            return json.loads(result.stdout)
        except FileNotFoundError:
            logger.warning('openclaw binary not found; returning []')
            return []
        except Exception as e:
            logger.warning(f'email adapter error: {e}')
            return []

class CalendarAdapter(RuntimeAdapter):
    def call(self, target: str, args: List[Any], context: Dict[str, Any]) -> Any:
        if target != 'G':
            raise AdapterError('calendar only supports G')
        try:
            result = _run_openclaw(
                ['openclaw', 'gog', 'calendar', 'get', '--limit', '10', '--json'],
                capture_output=True, text=True, timeout=10
            )
            if result.returncode != 0:
                logger.warning(f'calendar get failed: {result.stderr}')
                return []
            return json.loads(result.stdout)
        except FileNotFoundError:
            logger.warning('openclaw binary not found for calendar; returning []')
            return []
        except Exception as e:
            logger.warning(f'calendar adapter error: {e}')
            return []

class SocialAdapter(RuntimeAdapter):
    def call(self, target: str, args: List[Any], context: Dict[str, Any]) -> Any:
        if target != 'G':
            raise AdapterError('social only supports G')
        query = os.getenv('SOCIAL_MONITOR_QUERY', '"Steven Hooley"')
        try:
            result = _run_openclaw(
                ['openclaw', 'web', 'search', '--query', query, '--count', '10', '--json'],
                capture_output=True, text=True, timeout=15
            )
            if result.returncode != 0:
                logger.warning(f'web search failed: {result.stderr}')
                return []
            results = json.loads(result.stdout)
            now = int(time.time())
            mentions = []
            for r in results:
                mentions.append({
                    'id': r.get('url', str(hash(r.get('title', '')))[:8]),
                    'text': r.get('title', '') + '\n' + r.get('snippet', ''),
                    'ts': now
                })
            return mentions
        except FileNotFoundError:
            logger.warning('openclaw binary not found for web search; returning []')
            return []
        except Exception as e:
            logger.warning(f'social adapter error: {e}')
            return []

class ServiceAdapter(RuntimeAdapter):
    """Adapter to check status of infrastructure services: caddy, cloudflared, maddy, crm."""
    def call(self, target: str, args: List[Any], context: Dict[str, Any]) -> Any:
        verb = str(target or "").lower()
        # Status checks
        if verb in ('caddy', 'cloudflared', 'maddy', 'crm'):
            # existing status logic
            try:
                if verb == 'caddy':
                    if self._port_listening(80) or self._port_listening(443):
                        return 'up'
                    return 'down'
                elif verb == 'crm':
                    if self._port_listening(3000):
                        try:
                            import subprocess
                            cmd = ['curl', '-s', '-o', '/dev/null', '-w', '%{http_code}', 'http://127.0.0.1:3000/health']
                            code = subprocess.check_output(cmd, text=True, timeout=3).strip()
                            return 'up' if code in ('200', '201', '204') else 'down'
                        except Exception:
                            return 'up'
                    return 'down'
                else:
                    return 'up' if self._process_running(verb) else 'down'
            except Exception as e:
                logger.warning(f'service status error for {verb}: {e}')
                return 'down'

        # Restart actions: `svc restart <service>`
        elif verb == 'restart':
            if not args:
                raise AdapterError('restart requires service name argument')
            service = str(args[0]).lower()
            if service not in ('caddy', 'cloudflared', 'maddy', 'crm'):
                raise AdapterError(f'unknown service for restart: {service}')
            return self._restart_service(service)

        else:
            raise AdapterError(f'svc unknown verb: {target}')

    def _port_listening(self, port: int) -> bool:
        try:
            out = subprocess.check_output(['lsof', '-i', f':{port}', '-sTCP:LISTEN'], text=True)
            return 'LISTEN' in out
        except subprocess.CalledProcessError:
            return False
        except FileNotFoundError:
            try:
                out = subprocess.check_output(['netstat', '-an'], text=True)
                return f'.{port} ' in out or f'.{port}\n' in out
            except:
                return False

    def _process_running(self, name: str) -> bool:
        """Check if a process with a command line containing 'name' is running."""
        try:
            out = subprocess.check_output(['pgrep', '-f', name], text=True)
            return bool(out.strip())
        except subprocess.CalledProcessError:
            return False
        except FileNotFoundError:
            return False

    def _restart_service(self, service: str) -> bool:
        """Attempt to restart the given service. Returns True if restart command succeeded."""
        try:
            if service == 'caddy':
                # caddy as a brew service
                cmd = ['brew', 'services', 'restart', 'caddy']
            elif service == 'cloudflared':
                cmd = ['brew', 'services', 'restart', 'cloudflared']
            elif service == 'maddy':
                cmd = ['brew', 'services', 'restart', 'maddy']
            elif service == 'crm':
                # Try common Node process management; fallback to killing port 3000 and starting
                # First, try to find and kill existing process
                try:
                    # Find PID listening on 3000 and kill
                    subprocess.run(['pkill', '-f', 'node.*3000'], capture_output=True, timeout=5)
                except Exception:
                    pass
                # Start CRM: attempt default location
                crm_dir = Path('/Users/clawdbot/.openclaw/workspace/crm')
                if (crm_dir / 'server.js').exists():
                    cmd = ['node', str(crm_dir / 'server.js')]
                else:
                    logger.warning('CRM restart: no server.js found; cannot restart')
                    return False
            else:
                return False
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            if result.returncode == 0:
                logger.info(f'Restarted {service}: {cmd}')
                return True
            else:
                logger.warning(f'Restart {service} failed: {result.stderr}')
                return False
        except Exception as e:
            logger.error(f'Restart exception for {service}: {e}')
            return False

class DBLeadsAdapter(RuntimeAdapter):
    def call(self, target: str, args: List[Any], context: Dict[str, Any]) -> Any:
        if target != 'F':
            raise AdapterError('db leads only supports F')
        leads_path = os.getenv('LEADS_CSV', '/Users/clawdbot/.openclaw/workspace/leads/lead_output.csv')
        try:
            import csv
            with open(leads_path, newline='') as f:
                reader = csv.DictReader(f)
                rows = list(reader)
            now = int(time.time())
            for r in rows:
                if 'updated_at' not in r or not r['updated_at']:
                    r['updated_at'] = now
                else:
                    try:
                        r['updated_at'] = int(r['updated_at'])
                    except:
                        r['updated_at'] = now
            return rows
        except Exception as e:
            logger.warning(f'DBLeadsAdapter error: {e}')
            return []

class TiktokAdapter(RuntimeAdapter):
    """Adapter for TikTok-related DB queries."""
    def call(self, target: str, args: List[Any], context: Dict[str, Any]) -> Any:
        db_path = '/Users/clawdbot/.openclaw/workspace/crm/prisma/dev.db'
        conn = sqlite3.connect(db_path)
        try:
            cur = conn.cursor()
            if target == 'F':
                # Fetch all TiktokReport records
                cur.execute("SELECT id, filename, path, videoCount, createdAt FROM TiktokReport ORDER BY createdAt DESC")
                rows = cur.fetchall()
                result = []
                for rid, filename, path, videoCount, createdAt in rows:
                    if createdAt:
                        try:
                            dt = datetime.fromisoformat(createdAt.replace('Z', '+00:00'))
                            ts = int(dt.timestamp())
                        except Exception:
                            ts = 0
                    else:
                        ts = 0
                    result.append({
                        'id': rid,
                        'filename': filename,
                        'path': path,
                        'videoCount': videoCount,
                        'createdAt': createdAt,
                        'createdAt_ts': ts,
                    })
                return result
            elif target == 'videos':
                # Fetch all TiktokVideo records with processedAt
                cur.execute("SELECT id, tiktokId, title, description, processedAt, createdAt FROM TiktokVideo ORDER BY processedAt DESC")
                rows = cur.fetchall()
                result = []
                for rid, tid, title, desc, processedAt, createdAt in rows:
                    if processedAt:
                        try:
                            dt = datetime.fromisoformat(processedAt.replace('Z', '+00:00'))
                            processed_ts = int(dt.timestamp())
                        except Exception:
                            processed_ts = 0
                    else:
                        processed_ts = 0
                    result.append({
                        'id': rid,
                        'tiktokId': tid,
                        'title': title,
                        'description': desc,
                        'processedAt': processedAt,
                        'processedAt_ts': processed_ts,
                    })
                return result
            elif target == 'recent':
                # Return count of TiktokVideo records processed in the last 24 hours
                cur.execute("SELECT COUNT(*) FROM TiktokVideo WHERE processedAt >= datetime('now', '-24 hours')")
                (count,) = cur.fetchone()
                return int(count or 0)
            else:
                raise AdapterError(f'tiktok adapter unsupported target: {target}')
        except Exception as e:
            logger.warning(f'TiktokAdapter error: {e}')
            raise
        finally:
            conn.close()


class WebAdapter(RuntimeAdapter):
    group = 'web'
    def __init__(self, model: Optional[str] = None):
        # Defer missing-key errors to call() so openclaw_monitor_registry() can build
        # without OPENROUTER (intelligence runners, tests, dry workflows).
        self.api_key = os.getenv('OPENROUTER_API_KEY')
        self.model = model or os.getenv('AINL_WEB_MODEL', 'perplexity/sonar')
    def call(self, target: str, args: List[Any], context: Dict[str, Any]):
        if not (self.api_key or "").strip():
            raise AdapterError('OPENROUTER_API_KEY not set')
        if target != 'search':
            raise AdapterError(f'web adapter unsupported target: {target}')
        if len(args) != 1 or not isinstance(args[0], str):
            raise AdapterError('web search requires a single string query')
        query = args[0]

        def do_request():
            resp = requests.post(
                'https://openrouter.ai/api/v1/chat/completions',
                headers={
                    'Authorization': f'Bearer {self.api_key}',
                    'HTTP-Referer': 'https://openclaw.ai',
                    'X-Title': 'OpenClaw Intelligence',
                },
                json={
                    'model': self.model,
                    'messages': [
                        {'role': 'system', 'content': 'You are a news search assistant. Return ONLY a valid JSON array of results. Each result is an object with keys "id" (source URL), "title" (headline), and "text" (snippet). No extra text, markdown, or formatting.'},
                        {'role': 'user', 'content': f'Search the web for: {query}. Provide 10 results as a pure JSON array.'}
                    ],
                    'temperature': 0.3,
                    'max_tokens': 1536,
                },
                timeout=60
            )
            return resp

        # Attempt once with extended timeout
        try:
            resp = do_request()
            resp.raise_for_status()
        except requests.RequestException as e:
            raise AdapterError(f'web search request failed: {e}')

        data = resp.json()
        message = data['choices'][0]['message']
        content = message.get('content', '')
        annotations = message.get('annotations', [])

        # Try to extract JSON array from content first
        content = content.strip()
        if content.startswith('```json'):
            content = content[7:]
        if content.endswith('```'):
            content = content[:-3]
        content = content.strip()

        # Parse JSON array
        results = None
        try:
            results = json.loads(content)
        except json.JSONDecodeError as e:
            # Extract first array if wrapper text exists
            start = content.find('[')
            end = content.rfind(']') + 1
            if start != -1 and end > start:
                try:
                    results = json.loads(content[start:end])
                except Exception:
                    results = None

        # Fallback: Use annotations (OpenRouter Perplexity Sonar returns citations in annotations)
        if (results is None or (isinstance(results, list) and len(results) == 0)) and annotations:
            results = []
            for ann in annotations:
                if isinstance(ann, dict) and ann.get('type') == 'url_citation':
                    uc = ann.get('url_citation', {})
                    results.append({
                        'id': uc.get('url', ''),
                        'title': uc.get('title', ''),
                        'text': uc.get('title', ''),  # use title as snippet if no text
                    })

        if results is None:
            raise AdapterError('web search: could not extract results from response')

        # Allow { "results": [...] }
        if isinstance(results, dict) and 'results' in results:
            results = results['results']
        if not isinstance(results, list):
            raise AdapterError('web search: expected list result')
        normalized = []
        for r in results:
            if isinstance(r, dict):
                normalized.append({
                    'id': r.get('id') or r.get('url') or '',
                    'title': r.get('title', ''),
                    'text': r.get('text') or r.get('snippet') or '',
                })
        return normalized


class NotificationQueueAdapter(RuntimeAdapter):
    def push(self, queue: str, value: Any) -> str:
        status = self.call("Put", [queue, value], {})
        return str(status or "queued")

    def call(self, target: str, args: List[Any], context: Dict[str, Any]) -> Any:
        if str(target or "").lower() != 'put':
            raise AdapterError('queue only supports Put')
        if len(args) < 2:
            raise AdapterError('Queue.Put requires (queue, payload)')
        queue_name, payload = args[0], args[1]
        if queue_name != 'notify':
            return None
        msg = self._format_message(payload)
        recipient = os.getenv('OPENCLAW_TARGET', '8626314045')
        channel = os.getenv('OPENCLAW_NOTIFY_CHANNEL', 'telegram')
        logger.info(f'Queue sending {channel} to {recipient}: {msg}')
        try:
            _run_openclaw(
                ['openclaw', 'message', 'send', '--channel', channel, '--target', recipient, '--message', msg],
                check=True, timeout=10
            )
            return 'sent'
        except FileNotFoundError:
            logger.warning('openclaw binary not found for messaging; printing to stdout')
            print(f'[Notification] {msg}')
            return 'logged'
        except subprocess.CalledProcessError as e:
            logger.warning(f'message send failed: {e}')
            print(f'[Notification] {msg}')
            return 'logged'
        except Exception as e:
            logger.warning(f'notification adapter error: {e}')
            return 'error'

    def _format_message(self, payload: Any) -> str:
        # Handle string payloads directly
        if isinstance(payload, str):
            return payload

        # Custom text overrides everything
        if 'text' in payload:
            return str(payload['text'])

        module = payload.get('module')
        ts = payload.get('ts')
        time_str = ''
        if ts:
            try:
                time_str = time.strftime('%Y-%m-%d %H:%M', time.localtime(ts))
            except Exception:
                time_str = str(ts)

        if module:
            # Module-specific formatting
            if module == 'infrastructure_watchdog':
                # Alert payloads may have 'service' and 'status'
                service = payload.get('service')
                if service:
                    status = payload.get('status', '?')
                    restart_attempted = payload.get('restart_attempted', False)
                    restart_ok = payload.get('restart_ok', None)
                    msg = f"Service {service} is {status}"
                    if restart_attempted:
                        if restart_ok is True:
                            msg += " (restarted successfully)"
                        elif restart_ok is False:
                            msg += " (restart failed)"
                        else:
                            msg += " (restarting)"
                else:
                    # Summary
                    caddy = payload.get('caddy', '?')
                    cloudflared = payload.get('cloudflared', '?')
                    maddy = payload.get('maddy', '?')
                    crm = payload.get('crm', '?')
                    any_down = payload.get('any_down', False)
                    services = f"caddy={caddy}, cloudflared={cloudflared}, maddy={maddy}, crm={crm}"
                    if any_down:
                        msg = f"⚠️ Infrastructure: service(s) down — {services}"
                    else:
                        msg = f"✅ Infrastructure: all services up — {services}"
                parts = [msg]
                if time_str:
                    parts.append(f"🕒 {time_str}")
                return ' | '.join(parts)

            elif module == 'tiktok_sla':
                recent_count = payload.get('recent_count', 0)
                video_fresh = payload.get('video_fresh', False)
                backup_fresh = payload.get('backup_fresh', False)
                breach = payload.get('breach', False)
                status_str = f"recent_reports={recent_count}, video_fresh={'ok' if video_fresh else 'stale'}, backup_fresh={'ok' if backup_fresh else 'stale'}"
                if breach:
                    msg = f"🔴 TikTok SLA breach — {status_str}"
                else:
                    msg = f"✅ TikTok SLA OK — {status_str}"
                parts = [msg]
                if time_str:
                    parts.append(f"🕒 {time_str}")
                return ' | '.join(parts)

            elif module == 'token_cost_tracker':
                cost_usd = payload.get('cost_usd', 0.0)
                limit_usd = payload.get('limit_usd', 0.0)
                limit_exceeded = payload.get('limit_exceeded', False)
                date = payload.get('date', '')
                cost_str = f"${cost_usd:.2f}"
                limit_str = f"${limit_usd:.2f}"
                # Token breakdown
                total_tok = payload.get('total_tokens', 0)
                prompt_tok = payload.get('total_prompt', 0)
                completion_tok = payload.get('total_completion', 0)
                model_names = payload.get('model_names', '')
                # Build message
                if limit_exceeded:
                    msg = f"🔴 Token cost limit exceeded — {cost_str} / {limit_str} ({date})"
                else:
                    msg = f"✅ Token costs — {cost_str} / {limit_str} ({date})"
                if total_tok:
                    msg += f" | tokens: total={total_tok}, prompt={prompt_tok}, completion={completion_tok}"
                if model_names:
                    msg += f" | models: {model_names}"
                parts = [msg]
                if time_str:
                    parts.append(f"🕒 {time_str}")
                return ' | '.join(parts)

            elif module == 'canary_sampler':
                targets = payload.get('targets', [])
                any_breach = payload.get('any_breach', False)
                parts_targets = []
                for t in targets:
                    name = t.get('name', '?')
                    status = t.get('status', '?')
                    slow = t.get('slow', False)
                    consecutive = t.get('consecutive', 0)
                    part = f"{name}: status={status}"
                    if slow:
                        part += f", slow x{consecutive}"
                    parts_targets.append(part)
                targets_str = '; '.join(parts_targets) if parts_targets else 'no targets'
                if any_breach:
                    msg = f"⚠️ Canary breach — {targets_str}"
                else:
                    msg = f"✅ Canary OK — {targets_str}"
                parts = [msg]
                if time_str:
                    parts.append(f"🕒 {time_str}")
                return ' | '.join(parts)

            elif module == 'lead_quality_audit':
                total = payload.get('total', 0)
                phone_ok = payload.get('phone_ok', 0)
                website_ok = payload.get('website_ok', 0)
                rating_ok = payload.get('rating_ok', 0)
                reviews_ok = payload.get('reviews_ok', 0)
                def pct(n):
                    return f"{(n/total*100):.0f}%" if total>0 else "0%"
                msg = f"Lead Quality Audit: total={total} | phone_ok={phone_ok} ({pct(phone_ok)}) | website_ok={website_ok} ({pct(website_ok)}) | rating_ok={rating_ok} ({pct(rating_ok)}) | reviews_ok={reviews_ok} ({pct(reviews_ok)})"
                parts = [msg]
                if time_str:
                    parts.append(f"🕒 {time_str}")
                return ' | '.join(parts)

            # Unknown module: fall back to generic

        # Legacy handling
        parts = []
        if 'email_count' in payload:
            parts.append(f"📧 Email: {payload['email_count']} new")
        if 'cal_count' in payload:
            parts.append(f"📅 Calendar: {payload['cal_count']} upcoming")
        if 'social_count' in payload:
            parts.append(f"💬 Social: {payload['social_count']} mentions")
        if 'leads_count' in payload:
            parts.append(f"📈 Leads: {payload['leads_count']} recent")
        if 'failed_services' in payload:
            failed = payload['failed_services']
            if failed:
                parts.append(f"⚠️ Services down: {failed}")
        if time_str:
            parts.append(f"🕒 {time_str}")
        return ' | '.join(parts) if parts else 'Monitor check complete.'

class CacheAdapter(RuntimeAdapter):
    def __init__(self):
        self.store: Dict[str, Dict[str, Any]] = {}
        self.path = os.getenv('MONITOR_CACHE_JSON', '/tmp/monitor_state.json')
        self._load()

    def _load(self):
        try:
            with open(self.path) as f:
                self.store = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            self.store = {}

    def _save(self):
        try:
            with open(self.path, 'w') as f:
                json.dump(self.store, f)
        except Exception as e:
            logger.warning(f'Cache save error: {e}')

    def get(self, namespace: str, key: str) -> Any:
        return self.store.get(namespace, {}).get(key)

    def set(self, namespace: str, key: str, value: Any, ttl_s: int = 0) -> None:
        self.store.setdefault(namespace, {})[key] = value
        self._save()

    def call(self, target: str, args: List[Any], context: Dict[str, Any]) -> Any:
        verb = str(target or "").lower()
        if verb == 'get':
            ns, key = args[0], args[1]
            return self.get(str(ns), str(key))
        elif verb == 'set':
            ns, key, value = args[0], args[1], args[2]
            self.set(str(ns), str(key), value)
            return None
        else:
            raise AdapterError('cache supports get/set')

def openclaw_monitor_registry(ir_types: Optional[Dict] = None):
    from runtime.adapters.base import AdapterRegistry
    reg = AdapterRegistry(allowed=[
        'core', 'db', 'email', 'calendar', 'social',
        'svc', 'cache', 'queue', 'wasm', 'extras', 'tiktok', 'agent', 'memory',
        'fs', 'http', 'web', 'embedding_memory',
    ])
    from runtime.adapters.builtins import CoreBuiltinAdapter
    reg.register('core', CoreBuiltinAdapter())
    reg.register('email', EmailAdapter())
    reg.register('calendar', CalendarAdapter())
    reg.register('social', SocialAdapter())
    reg.register('svc', ServiceAdapter())
    reg.register('db', DBLeadsAdapter())
    reg.register('cache', CacheAdapter())
    reg.register('queue', NotificationQueueAdapter())
    reg.register('extras', ExtrasAdapter())
    reg.register('tiktok', TiktokAdapter())
    reg.register('web', WebAdapter())
    reg.register('agent', AgentAdapter())
    # Memory adapter with extra 'intel' namespace for intelligence storage
    reg.register('memory', MemoryAdapter(valid_namespaces={'intel', 'workflow', 'session', 'long_term', 'daily_log', 'ops'}))

    from adapters.embedding_memory import EmbeddingMemoryAdapter
    reg.register('embedding_memory', EmbeddingMemoryAdapter())

    # Filesystem adapter sandboxed to workspace root
    from runtime.adapters.fs import SandboxedFileSystemAdapter
    workspace_root = os.getenv('AINL_FS_ROOT', '/Users/clawdbot/.openclaw/workspace')
    reg.register('fs', SandboxedFileSystemAdapter(
        sandbox_root=workspace_root,
        max_read_bytes=2_000_000,
        max_write_bytes=2_000_000,
        allow_delete=False,
    ))

    # HTTP adapter for LLM calls and general HTTP
    from runtime.adapters.http import SimpleHttpAdapter
    reg.register('http', SimpleHttpAdapter())

    # Optional WASM adapter if wasmtime is available and demo modules exist
    try:
        from runtime.adapters.wasm import WasmAdapter
        base = Path(__file__).resolve().parent.parent
        modules = {}
        for name in ('metrics', 'health'):
            for ext in ('.wasm', '.wat'):
                p = base / 'demo' / 'wasm' / f'{name}{ext}'
                if p.is_file():
                    modules[name] = str(p)
                    break
        # Only include modules that exist
        available = {k: v for k, v in modules.items() if Path(v).exists()}
        if available:
            reg.register('wasm', WasmAdapter(modules=available))
    except Exception as e:
        logger.warning(f'WASM adapter not registered: {e}')

    return reg
