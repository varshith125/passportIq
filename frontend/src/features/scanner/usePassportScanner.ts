import { useCallback, useRef, useState } from 'react';
import { ApiRequestError, extractPassportFromImage } from '../../services/api';
import type { PassportExtractionResponse } from '../../types/passport';

export const MAX_UPLOAD_BYTES = 200 * 1024 * 1024; // 200 MB

export type ScannerPhase = 'idle' | 'uploading' | 'completed' | 'error';

export interface ClientValidationError {
  code: string;
  message: string;
}

export interface ScanSessionRecord {
  id: string;
  timestamp: string;
  fileName: string;
  fileSize: number;
  file: File;
  result: PassportExtractionResponse;
}

export function validateClientFile(file: File): ClientValidationError | null {
  if (file.size === 0) {
    return {
      code: 'EMPTY_FILE',
      message: 'The selected file is empty (0 bytes). Please select a valid document or image.',
    };
  }

  if (file.size > MAX_UPLOAD_BYTES) {
    const sizeMb = (file.size / (1024 * 1024)).toFixed(2);
    return {
      code: 'FILE_TOO_LARGE',
      message: `File size (${sizeMb} MB) exceeds the maximum upload limit of 200 MB.`,
    };
  }

  return null;
}

export function usePassportScanner() {
  const [phase, setPhase] = useState<ScannerPhase>('idle');
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [result, setResult] = useState<PassportExtractionResponse | null>(null);
  const [errorCode, setErrorCode] = useState<string | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [sessionHistory, setSessionHistory] = useState<ScanSessionRecord[]>([]);

  const abortControllerRef = useRef<AbortController | null>(null);
  const latestRequestIdRef = useRef<number>(0);

  const startExtraction = useCallback(async (file: File) => {
    const currentRequestId = ++latestRequestIdRef.current;

    const validationErr = validateClientFile(file);
    if (validationErr) {
      setSelectedFile(file);
      setResult(null);
      setErrorCode(validationErr.code);
      setErrorMessage(validationErr.message);
      setPhase('error');
      return;
    }

    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
    }
    const controller = new AbortController();
    abortControllerRef.current = controller;

    setSelectedFile(file);
    setResult(null);
    setErrorCode(null);
    setErrorMessage(null);
    setPhase('uploading');

    try {
      const response = await extractPassportFromImage(file, controller.signal);
      // Guard against race conditions if another file was uploaded while this was in-flight
      if (currentRequestId === latestRequestIdRef.current) {
        setResult(response);
        setPhase('completed');

        const newRecord: ScanSessionRecord = {
          id: `scan-${Date.now()}-${Math.random().toString(36).substring(2, 7)}`,
          timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' }),
          fileName: file.name,
          fileSize: file.size,
          file,
          result: response,
        };
        setSessionHistory((prev) => [newRecord, ...prev]);
      }
    } catch (err) {
      if (err instanceof DOMException && err.name === 'AbortError') {
        if (currentRequestId === latestRequestIdRef.current) {
          setPhase('idle');
        }
        return;
      }

      if (currentRequestId === latestRequestIdRef.current) {
        if (err instanceof ApiRequestError) {
          setErrorCode(err.code);
          setErrorMessage(err.message);
        } else {
          setErrorCode('UNEXPECTED_CLIENT_ERROR');
          setErrorMessage(
            err instanceof Error ? err.message : 'An unexpected error occurred during extraction.',
          );
        }
        setPhase('error');
      }
    }
  }, []);

  const retryExtraction = useCallback(() => {
    if (selectedFile) {
      void startExtraction(selectedFile);
    }
  }, [selectedFile, startExtraction]);

  const loadSessionRecord = useCallback((record: ScanSessionRecord) => {
    setSelectedFile(record.file);
    setResult(record.result);
    setErrorCode(null);
    setErrorMessage(null);
    setPhase('completed');
  }, []);

  const clearSessionHistory = useCallback(() => {
    setSessionHistory([]);
  }, []);

  const resetScanner = useCallback(() => {
    latestRequestIdRef.current++;
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
      abortControllerRef.current = null;
    }
    setPhase('idle');
    setSelectedFile(null);
    setResult(null);
    setErrorCode(null);
    setErrorMessage(null);
  }, []);

  return {
    phase,
    selectedFile,
    result,
    errorCode,
    errorMessage,
    sessionHistory,
    startExtraction,
    retryExtraction,
    resetScanner,
    loadSessionRecord,
    clearSessionHistory,
  };
}
