import '@testing-library/jest-dom';
import { beforeEach, vi } from 'vitest';

const matchMediaFunction = (query: string) => ({
  matches: false,
  media: query,
  onchange: null,
  addListener: () => {},
  removeListener: () => {},
  addEventListener: () => {},
  removeEventListener: () => {},
  dispatchEvent: () => true,
});

const setupWindowMocks = () => {
  if (typeof window === 'undefined') return;

  if (!window.URL.createObjectURL) {
    window.URL.createObjectURL = vi.fn(() => 'blob:mock-passport-image');
  }
  if (!window.URL.revokeObjectURL) {
    window.URL.revokeObjectURL = vi.fn();
  }
  window.scrollTo = (() => {}) as unknown as typeof window.scrollTo;

  Object.defineProperty(window, 'matchMedia', {
    writable: true,
    configurable: true,
    value: matchMediaFunction,
  });
};

setupWindowMocks();

beforeEach(() => {
  setupWindowMocks();
});


