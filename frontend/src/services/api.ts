import type {
  ApiErrorResponse,
  PassportExtractionResponse,
} from '../types/passport';

export class ApiRequestError extends Error {
  public readonly code: string;
  public readonly statusCode: number;
  public readonly details?: Record<string, unknown>;

  constructor(
    code: string,
    message: string,
    statusCode: number,
    details?: Record<string, unknown>,
  ) {
    super(message);
    this.name = 'ApiRequestError';
    this.code = code;
    this.statusCode = statusCode;
    this.details = details;
  }
}

const API_BASE_URL = (import.meta.env?.VITE_API_BASE_URL as string | undefined) ?? '';

/**
 * Send an uploaded passport image to POST /api/passports/extract.
 */
export async function extractPassportFromImage(
  file: File,
  signal?: AbortSignal,
): Promise<PassportExtractionResponse> {
  const formData = new FormData();
  formData.append('file', file);

  let response: Response;
  try {
    response = await fetch(`${API_BASE_URL}/api/passports/extract`, {
      method: 'POST',
      body: formData,
      signal,
    });
  } catch (err) {
    if (err instanceof DOMException && err.name === 'AbortError') {
      throw err;
    }
    throw new ApiRequestError(
      'NETWORK_ERROR',
      'Unable to reach the PassPortIQ extraction service. Verify that the backend server is running.',
      0,
    );
  }

  if (!response.ok) {
    let errorBody: ApiErrorResponse | null = null;
    try {
      errorBody = (await response.json()) as ApiErrorResponse;
    } catch {
      errorBody = null;
    }

    if (errorBody?.error) {
      throw new ApiRequestError(
        errorBody.error.code,
        errorBody.error.message,
        response.status,
        errorBody.error.details,
      );
    }

    throw new ApiRequestError(
      `HTTP_${response.status}`,
      `Extraction request failed with HTTP status ${response.status}.`,
      response.status,
    );
  }

  return (await response.json()) as PassportExtractionResponse;
}

export interface BackendHealthResponse {
  status: string;
  ready: boolean;
  service: string;
  version: string;
  ocr?: {
    engine?: string;
    ready?: boolean;
    available_engines?: string[];
  };
}

/**
 * Fetch backend readiness status from GET /health/ready.
 */
export async function fetchBackendHealth(): Promise<BackendHealthResponse> {
  try {
    const response = await fetch(`${API_BASE_URL}/health/ready`, {
      headers: { Accept: 'application/json' },
    });
    if (!response.ok) {
      throw new Error(`Health check returned HTTP ${response.status}`);
    }
    return (await response.json()) as BackendHealthResponse;
  } catch (err) {
    return {
      status: 'offline',
      ready: false,
      service: 'PassPortIQ',
      version: '2.0.0',
    };
  }
}

