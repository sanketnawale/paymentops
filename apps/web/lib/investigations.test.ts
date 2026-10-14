import { afterEach, describe, expect, it, vi } from 'vitest';
import { getInvestigation, listDemoCases, listInvestigations, startInvestigation } from './api';

function mockResponse(status: number, body: unknown): Response {
  return {
    ok: status >= 200 && status < 300,
    status,
    json: async () => body,
  } as unknown as Response;
}

type FetchHandler = (url: string, init?: RequestInit) => Response;

function fetchStub(handler: FetchHandler) {
  return vi.fn(async (url: string | URL, init?: RequestInit) => handler(String(url), init));
}

afterEach(() => {
  vi.restoreAllMocks();
});

describe('investigation api client', () => {
  it('lists synthetic demo cases from the backend path', async () => {
    const fetchMock = fetchStub(() => mockResponse(200, [{ key: 'pacs008-valid' }]));
    vi.stubGlobal('fetch', fetchMock);
    const cases = await listDemoCases();
    expect(cases[0].key).toBe('pacs008-valid');
    expect(fetchMock.mock.calls[0][0]).toContain('/api/v1/investigations/demo-cases');
  });

  it('starts an investigation with a POST body containing only the demo case key', async () => {
    const fetchMock = fetchStub(() =>
      mockResponse(201, { investigation_id: 'inv-1', status: 'RUNNING' }),
    );
    vi.stubGlobal('fetch', fetchMock);
    const investigation = await startInvestigation('pacs008-missing-town');
    expect(investigation.investigation_id).toBe('inv-1');
    const init = fetchMock.mock.calls[0][1];
    expect(init?.method).toBe('POST');
    expect(String(init?.body)).toContain('pacs008-missing-town');
    // The browser never sends credentials; the proxy injects them server-side.
    const headers = (init?.headers ?? {}) as Record<string, string>;
    expect(Object.keys(headers).map((k) => k.toLowerCase())).not.toContain('authorization');
  });

  it('fetches an investigation by id', async () => {
    const fetchMock = fetchStub(() => mockResponse(200, { investigation_id: 'inv-9' }));
    vi.stubGlobal('fetch', fetchMock);
    await getInvestigation('inv-9');
    expect(fetchMock.mock.calls[0][0]).toContain('/api/v1/investigations/inv-9');
  });

  it('lists investigations scoped to the operator tenant', async () => {
    const fetchMock = fetchStub(() => mockResponse(200, []));
    vi.stubGlobal('fetch', fetchMock);
    await listInvestigations();
    expect(fetchMock.mock.calls[0][0]).toContain('/api/v1/investigations?limit=50');
  });
});
