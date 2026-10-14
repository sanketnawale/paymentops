import { afterEach, describe, expect, it, vi } from 'vitest';
import { ApiError, apiJson } from './api';

function mockResponse(status: number, body: unknown): Response {
  return {
    ok: status >= 200 && status < 300,
    status,
    json: async () => body,
  } as unknown as Response;
}

afterEach(() => {
  vi.restoreAllMocks();
});

describe('apiJson error handling', () => {
  it('returns parsed JSON on success', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => mockResponse(200, { ok: true })));
    await expect(apiJson<{ ok: boolean }>('/api/v1/info')).resolves.toEqual({ ok: true });
  });

  it('maps structured string detail into ApiError', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => mockResponse(422, { detail: 'unsupported ISO version: camt.052' })));
    await expect(apiJson('/api/v1/iso/analyze', { method: 'POST' })).rejects.toThrowError(
      'unsupported ISO version: camt.052',
    );
  });

  it('maps auth failure to a friendly message', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => mockResponse(401, {})));
    await expect(apiJson('/api/v1/dashboard')).rejects.toMatchObject({ status: 401 });
  });

  it('maps validation arrays to a message', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => mockResponse(422, { detail: [{ msg: 'Field required' }] })));
    await expect(apiJson('/api/v1/batches', { method: 'POST' })).rejects.toThrowError('Field required');
  });

  it('maps network failure to ApiError with status 0', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => {
      throw new TypeError('failed to fetch');
    }));
    const err = (await apiJson('/api/v1/dashboard').catch((e) => e)) as ApiError;
    expect(err).toBeInstanceOf(ApiError);
    expect(err.status).toBe(0);
  });
});
