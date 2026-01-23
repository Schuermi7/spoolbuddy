import { useState, useEffect } from "preact/hooks";
import { ChevronDown, ChevronRight, Play, Copy, Loader2, ExternalLink, AlertCircle, CheckCircle } from "lucide-preact";

interface OpenAPISchema {
  paths: Record<string, Record<string, EndpointSpec>>;
  components?: {
    schemas?: Record<string, SchemaSpec>;
  };
}

interface EndpointSpec {
  summary?: string;
  description?: string;
  tags?: string[];
  parameters?: ParameterSpec[];
  requestBody?: {
    content?: {
      'application/json'?: {
        schema?: SchemaSpec;
      };
    };
  };
  responses?: Record<string, ResponseSpec>;
}

interface ParameterSpec {
  name: string;
  in: 'path' | 'query' | 'header';
  required?: boolean;
  description?: string;
  schema?: {
    type?: string;
    default?: unknown;
    enum?: string[];
  };
}

interface SchemaSpec {
  type?: string;
  properties?: Record<string, SchemaSpec>;
  required?: string[];
  items?: SchemaSpec;
  $ref?: string;
  allOf?: SchemaSpec[];
  anyOf?: SchemaSpec[];
  oneOf?: SchemaSpec[];
  default?: unknown;
  description?: string;
  enum?: string[];
  example?: unknown;
}

interface ResponseSpec {
  description?: string;
  content?: {
    'application/json'?: {
      schema?: SchemaSpec;
    };
  };
}

interface APIResponse {
  status: number;
  statusText: string;
  headers: Record<string, string>;
  body: unknown;
  duration: number;
}

const METHOD_COLORS: Record<string, string> = {
  get: 'bg-blue-500/20 text-blue-400 border-blue-500/30',
  post: 'bg-green-500/20 text-green-400 border-green-500/30',
  put: 'bg-yellow-500/20 text-yellow-400 border-yellow-500/30',
  patch: 'bg-orange-500/20 text-orange-400 border-orange-500/30',
  delete: 'bg-red-500/20 text-red-400 border-red-500/30',
};

function resolveRef(schema: OpenAPISchema, ref: string): SchemaSpec {
  const parts = ref.replace('#/', '').split('/');
  let current: unknown = schema;
  for (const part of parts) {
    current = (current as Record<string, unknown>)[part];
  }
  return current as SchemaSpec;
}

function getSchemaExample(schema: OpenAPISchema, spec: SchemaSpec, depth = 0): unknown {
  if (depth > 5) return '...';

  if (spec.$ref) {
    return getSchemaExample(schema, resolveRef(schema, spec.$ref), depth + 1);
  }

  if (spec.allOf) {
    const merged: Record<string, unknown> = {};
    for (const sub of spec.allOf) {
      const subExample = getSchemaExample(schema, sub, depth + 1);
      if (typeof subExample === 'object' && subExample !== null) {
        Object.assign(merged, subExample);
      }
    }
    return merged;
  }

  if (spec.example !== undefined) return spec.example;
  if (spec.default !== undefined) return spec.default;

  switch (spec.type) {
    case 'string':
      if (spec.enum) return spec.enum[0];
      return 'string';
    case 'integer':
    case 'number':
      return 0;
    case 'boolean':
      return false;
    case 'array':
      return spec.items ? [getSchemaExample(schema, spec.items, depth + 1)] : [];
    case 'object':
      if (spec.properties) {
        const obj: Record<string, unknown> = {};
        for (const [key, propSpec] of Object.entries(spec.properties)) {
          obj[key] = getSchemaExample(schema, propSpec, depth + 1);
        }
        return obj;
      }
      return {};
    default:
      return null;
  }
}

interface EndpointItemProps {
  path: string;
  method: string;
  spec: EndpointSpec;
  schema: OpenAPISchema;
  apiKey: string;
}

function EndpointItem({ path, method, spec, schema, apiKey }: EndpointItemProps) {
  const [expanded, setExpanded] = useState(false);
  const [params, setParams] = useState<Record<string, string>>({});
  const [bodyText, setBodyText] = useState('');
  const [response, setResponse] = useState<APIResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [copied, setCopied] = useState(false);

  // Initialize params with defaults
  useEffect(() => {
    if (expanded && spec.parameters) {
      const defaults: Record<string, string> = {};
      for (const param of spec.parameters) {
        if (param.schema?.default !== undefined) {
          defaults[param.name] = String(param.schema.default);
        }
      }
      setParams(prev => ({ ...defaults, ...prev }));
    }
  }, [expanded, spec.parameters]);

  // Initialize body with example
  useEffect(() => {
    if (expanded && spec.requestBody?.content?.['application/json']?.schema && !bodyText) {
      const bodySchema = spec.requestBody.content['application/json'].schema;
      const example = getSchemaExample(schema, bodySchema);
      setBodyText(JSON.stringify(example, null, 2));
    }
  }, [expanded, spec.requestBody, schema, bodyText]);

  const getMissingParams = () => {
    const missing: string[] = [];
    for (const param of spec.parameters || []) {
      if (param.in === 'path' || param.required) {
        const value = params[param.name];
        if (value === undefined || value === '') {
          missing.push(param.name);
        }
      }
    }
    return missing;
  };

  const missingParams = getMissingParams();

  const executeRequest = async () => {
    if (missingParams.length > 0) {
      setResponse({
        status: 0,
        statusText: 'Validation Error',
        headers: {},
        body: `Missing required parameters: ${missingParams.join(', ')}`,
        duration: 0,
      });
      return;
    }

    setLoading(true);
    setResponse(null);

    try {
      let url = path;
      const queryParams = new URLSearchParams();

      for (const param of spec.parameters || []) {
        const value = params[param.name];
        if (value !== undefined && value !== '') {
          if (param.in === 'path') {
            url = url.replace(`{${param.name}}`, encodeURIComponent(value));
          } else if (param.in === 'query') {
            queryParams.append(param.name, value);
          }
        }
      }

      const queryString = queryParams.toString();
      const fullUrl = `${url}${queryString ? `?${queryString}` : ''}`;

      const headers: Record<string, string> = {
        'Content-Type': 'application/json',
      };

      if (apiKey) {
        headers['X-API-Key'] = apiKey;
      }

      const options: RequestInit = {
        method: method.toUpperCase(),
        headers,
      };

      if (['post', 'put', 'patch'].includes(method) && bodyText) {
        options.body = bodyText;
      }

      const startTime = performance.now();
      const res = await fetch(fullUrl, options);
      const duration = Math.round(performance.now() - startTime);

      const responseHeaders: Record<string, string> = {};
      res.headers.forEach((value, key) => {
        responseHeaders[key] = value;
      });

      let body: unknown;
      const contentType = res.headers.get('content-type');
      if (contentType?.includes('application/json')) {
        body = await res.json();
      } else {
        body = await res.text();
      }

      setResponse({
        status: res.status,
        statusText: res.statusText,
        headers: responseHeaders,
        body,
        duration,
      });
    } catch (err) {
      setResponse({
        status: 0,
        statusText: 'Network Error',
        headers: {},
        body: err instanceof Error ? err.message : 'Unknown error',
        duration: 0,
      });
    } finally {
      setLoading(false);
    }
  };

  const copyResponse = async () => {
    if (response) {
      const text = typeof response.body === 'string'
        ? response.body
        : JSON.stringify(response.body, null, 2);
      try {
        if (navigator.clipboard && navigator.clipboard.writeText) {
          await navigator.clipboard.writeText(text);
        } else {
          const textArea = document.createElement('textarea');
          textArea.value = text;
          textArea.style.position = 'fixed';
          textArea.style.left = '-999999px';
          document.body.appendChild(textArea);
          textArea.select();
          document.execCommand('copy');
          document.body.removeChild(textArea);
        }
        setCopied(true);
        setTimeout(() => setCopied(false), 2000);
      } catch {
        // Silently fail
      }
    }
  };

  const pathParams = (spec.parameters || []).filter(p => p.in === 'path');
  const queryParamsSpec = (spec.parameters || []).filter(p => p.in === 'query');
  const hasBody = ['post', 'put', 'patch'].includes(method) && spec.requestBody;

  return (
    <div class="border border-[var(--border-color)] rounded-lg overflow-hidden">
      <button
        onClick={() => setExpanded(!expanded)}
        class="w-full flex items-center gap-3 p-3 hover:bg-[var(--bg-tertiary)]/50 transition-colors text-left"
      >
        {expanded ? (
          <ChevronDown class="w-4 h-4 text-[var(--text-muted)] flex-shrink-0" />
        ) : (
          <ChevronRight class="w-4 h-4 text-[var(--text-muted)] flex-shrink-0" />
        )}
        <span class={`px-2 py-0.5 text-xs font-mono font-semibold uppercase rounded border ${METHOD_COLORS[method] || 'bg-gray-500/20 text-gray-400'}`}>
          {method}
        </span>
        <code class="text-sm text-[var(--text-primary)] font-mono flex-1 truncate">{path}</code>
        {spec.summary && (
          <span class="text-sm text-[var(--text-muted)] truncate max-w-[40%]">{spec.summary}</span>
        )}
      </button>

      {expanded && (
        <div class="border-t border-[var(--border-color)] p-4 space-y-4 bg-[var(--bg-secondary)]/50">
          {spec.description && (
            <p class="text-sm text-[var(--text-muted)]">{spec.description}</p>
          )}

          {/* Path Parameters */}
          {pathParams.length > 0 && (
            <div class="space-y-2">
              <h4 class="text-sm font-medium text-[var(--text-primary)]">Path Parameters</h4>
              <div class="space-y-2">
                {pathParams.map(param => (
                  <div key={param.name} class="flex items-center gap-2">
                    <label class="text-sm text-[var(--text-muted)] w-32 flex-shrink-0">
                      {param.name}
                      {param.required && <span class="text-red-400 ml-1">*</span>}
                    </label>
                    <input
                      type="text"
                      value={params[param.name] || ''}
                      onInput={(e) => setParams(p => ({ ...p, [param.name]: (e.target as HTMLInputElement).value }))}
                      placeholder={param.description || param.schema?.type || 'value'}
                      class="flex-1 px-2 py-1 bg-[var(--bg-secondary)] border border-[var(--border-color)] rounded text-[var(--text-primary)] text-sm font-mono focus:border-[var(--accent)] focus:outline-none"
                    />
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Query Parameters */}
          {queryParamsSpec.length > 0 && (
            <div class="space-y-2">
              <h4 class="text-sm font-medium text-[var(--text-primary)]">Query Parameters</h4>
              <div class="space-y-2">
                {queryParamsSpec.map(param => (
                  <div key={param.name} class="flex items-center gap-2">
                    <label class="text-sm text-[var(--text-muted)] w-32 flex-shrink-0">
                      {param.name}
                      {param.required && <span class="text-red-400 ml-1">*</span>}
                    </label>
                    {param.schema?.enum ? (
                      <select
                        value={params[param.name] || ''}
                        onChange={(e) => setParams(p => ({ ...p, [param.name]: (e.target as HTMLSelectElement).value }))}
                        class="flex-1 px-2 py-1 bg-[var(--bg-secondary)] border border-[var(--border-color)] rounded text-[var(--text-primary)] text-sm focus:border-[var(--accent)] focus:outline-none"
                      >
                        <option value="">-- Select --</option>
                        {param.schema.enum.map(opt => (
                          <option key={opt} value={opt}>{opt}</option>
                        ))}
                      </select>
                    ) : (
                      <input
                        type="text"
                        value={params[param.name] || ''}
                        onInput={(e) => setParams(p => ({ ...p, [param.name]: (e.target as HTMLInputElement).value }))}
                        placeholder={param.description || param.schema?.type || 'value'}
                        class="flex-1 px-2 py-1 bg-[var(--bg-secondary)] border border-[var(--border-color)] rounded text-[var(--text-primary)] text-sm font-mono focus:border-[var(--accent)] focus:outline-none"
                      />
                    )}
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Request Body */}
          {hasBody && (
            <div class="space-y-2">
              <h4 class="text-sm font-medium text-[var(--text-primary)]">Request Body</h4>
              <textarea
                value={bodyText}
                onInput={(e) => setBodyText((e.target as HTMLTextAreaElement).value)}
                rows={8}
                class="w-full px-3 py-2 bg-[var(--bg-secondary)] border border-[var(--border-color)] rounded-lg text-[var(--text-primary)] text-sm font-mono focus:border-[var(--accent)] focus:outline-none resize-y"
                placeholder="JSON request body..."
              />
            </div>
          )}

          {/* Execute Button */}
          <div class="flex items-center gap-2">
            <button onClick={executeRequest} disabled={loading} class="btn btn-primary flex items-center gap-2">
              {loading ? (
                <Loader2 class="w-4 h-4 animate-spin" />
              ) : (
                <Play class="w-4 h-4" />
              )}
              Execute
            </button>
            {missingParams.length > 0 && (
              <span class="text-xs text-yellow-400 flex items-center gap-1">
                <AlertCircle class="w-3 h-3" />
                Fill in: {missingParams.join(', ')}
              </span>
            )}
          </div>

          {/* Response */}
          {response && (
            <div class="space-y-2">
              <div class="flex items-center justify-between">
                <h4 class="text-sm font-medium text-[var(--text-primary)] flex items-center gap-2">
                  Response
                  <span class={`px-2 py-0.5 text-xs rounded ${
                    response.status >= 200 && response.status < 300
                      ? 'bg-green-500/20 text-green-400'
                      : response.status >= 400
                        ? 'bg-red-500/20 text-red-400'
                        : 'bg-yellow-500/20 text-yellow-400'
                  }`}>
                    {response.status} {response.statusText}
                  </span>
                  <span class="text-xs text-[var(--text-muted)]">{response.duration}ms</span>
                </h4>
                <button class="btn btn-ghost p-1" onClick={copyResponse}>
                  {copied ? (
                    <CheckCircle class="w-4 h-4 text-green-400" />
                  ) : (
                    <Copy class="w-4 h-4" />
                  )}
                </button>
              </div>
              <pre class="p-3 bg-[var(--bg-secondary)] rounded-lg text-sm font-mono text-[var(--text-primary)] overflow-auto max-h-96 border border-[var(--border-color)]">
                {typeof response.body === 'string'
                  ? response.body
                  : JSON.stringify(response.body, null, 2)}
              </pre>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

interface APIBrowserProps {
  apiKey?: string;
}

export function APIBrowser({ apiKey = '' }: APIBrowserProps) {
  const [schema, setSchema] = useState<OpenAPISchema | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [expandedTags, setExpandedTags] = useState<Set<string>>(new Set());
  const [searchQuery, setSearchQuery] = useState('');

  useEffect(() => {
    async function fetchSchema() {
      try {
        const res = await fetch('/api/openapi.json');
        if (!res.ok) throw new Error('Failed to fetch OpenAPI schema');
        const data = await res.json();
        setSchema(data);
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Unknown error');
      } finally {
        setLoading(false);
      }
    }
    fetchSchema();
  }, []);

  if (loading) {
    return (
      <div class="flex justify-center py-12">
        <Loader2 class="w-8 h-8 text-[var(--accent)] animate-spin" />
      </div>
    );
  }

  if (error || !schema) {
    return (
      <div class="card">
        <div class="p-8 text-center text-red-400">
          <AlertCircle class="w-12 h-12 mx-auto mb-3 opacity-50" />
          <p>Failed to load API schema</p>
          <p class="text-sm text-[var(--text-muted)] mt-1">{error}</p>
        </div>
      </div>
    );
  }

  // Group endpoints by tag
  const endpointsByTag: Record<string, Array<{ path: string; method: string; spec: EndpointSpec }>> = {};

  for (const [path, methods] of Object.entries(schema.paths)) {
    for (const [method, spec] of Object.entries(methods)) {
      if (method === 'parameters') continue;

      const tags = spec.tags || ['Other'];
      for (const tag of tags) {
        if (!endpointsByTag[tag]) {
          endpointsByTag[tag] = [];
        }
        endpointsByTag[tag].push({ path, method, spec });
      }
    }
  }

  // Filter endpoints based on search
  const filteredTags = Object.entries(endpointsByTag)
    .map(([tag, endpoints]) => {
      if (!searchQuery) return { tag, endpoints };

      const filtered = endpoints.filter(({ path, method, spec }) => {
        const searchLower = searchQuery.toLowerCase();
        return (
          path.toLowerCase().includes(searchLower) ||
          method.toLowerCase().includes(searchLower) ||
          (spec.summary?.toLowerCase() || '').includes(searchLower) ||
          (spec.description?.toLowerCase() || '').includes(searchLower)
        );
      });

      return { tag, endpoints: filtered };
    })
    .filter(({ endpoints }) => endpoints.length > 0)
    .sort((a, b) => a.tag.localeCompare(b.tag));

  const toggleTag = (tag: string) => {
    setExpandedTags(prev => {
      const next = new Set(prev);
      if (next.has(tag)) {
        next.delete(tag);
      } else {
        next.add(tag);
      }
      return next;
    });
  };

  const expandAll = () => {
    setExpandedTags(new Set(filteredTags.map(t => t.tag)));
  };

  const collapseAll = () => {
    setExpandedTags(new Set());
  };

  return (
    <div class="space-y-4">
      {/* Header */}
      <div class="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
        <div class="flex-1 w-full sm:w-auto">
          <input
            type="text"
            value={searchQuery}
            onInput={(e) => setSearchQuery((e.target as HTMLInputElement).value)}
            placeholder="Search endpoints..."
            class="w-full sm:max-w-md px-3 py-2 bg-[var(--bg-secondary)] border border-[var(--border-color)] rounded-lg text-[var(--text-primary)] focus:border-[var(--accent)] focus:outline-none"
          />
        </div>
        <div class="flex items-center gap-2">
          <button class="btn btn-ghost text-sm" onClick={expandAll}>
            Expand All
          </button>
          <button class="btn btn-ghost text-sm" onClick={collapseAll}>
            Collapse All
          </button>
          <a
            href="/api/docs"
            target="_blank"
            rel="noopener noreferrer"
            class="flex items-center gap-1 text-sm text-[var(--accent)] hover:underline"
          >
            <ExternalLink class="w-4 h-4" />
            Swagger UI
          </a>
        </div>
      </div>

      {/* Endpoint count */}
      <p class="text-sm text-[var(--text-muted)]">
        {filteredTags.reduce((acc, t) => acc + t.endpoints.length, 0)} endpoints in {filteredTags.length} categories
      </p>

      {/* Endpoints by Tag */}
      <div class="space-y-3">
        {filteredTags.map(({ tag, endpoints }) => (
          <div key={tag} class="card overflow-hidden">
            <button
              onClick={() => toggleTag(tag)}
              class="w-full flex items-center justify-between p-4 hover:bg-[var(--bg-tertiary)]/30 transition-colors text-left"
            >
              <div class="flex items-center gap-2">
                {expandedTags.has(tag) ? (
                  <ChevronDown class="w-5 h-5 text-[var(--text-muted)]" />
                ) : (
                  <ChevronRight class="w-5 h-5 text-[var(--text-muted)]" />
                )}
                <h3 class="text-base font-semibold text-[var(--text-primary)] capitalize">{tag.replace(/-/g, ' ')}</h3>
                <span class="text-xs bg-[var(--bg-tertiary)] px-2 py-0.5 rounded-full text-[var(--text-muted)]">
                  {endpoints.length}
                </span>
              </div>
            </button>

            {expandedTags.has(tag) && (
              <div class="px-4 pb-4 space-y-2">
                {endpoints.map(({ path, method, spec }) => (
                  <EndpointItem
                    key={`${method}-${path}`}
                    path={path}
                    method={method}
                    spec={spec}
                    schema={schema}
                    apiKey={apiKey}
                  />
                ))}
              </div>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}
