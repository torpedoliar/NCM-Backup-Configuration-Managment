import '@testing-library/jest-dom/vitest';

class ResizeObserverMock {
  observe() {}
  unobserve() {}
  disconnect() {}
}

(globalThis as unknown as { ResizeObserver: typeof ResizeObserverMock }).ResizeObserver = ResizeObserverMock;
