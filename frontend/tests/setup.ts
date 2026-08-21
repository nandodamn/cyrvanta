import "@testing-library/jest-dom";

// jsdom does not implement matchMedia, and the shell asks it which theme the
// machine prefers. Reported as "no light preference" so tests see the dark
// default; individual tests override this to exercise the other branch.
if (!window.matchMedia) {
  window.matchMedia = (query: string) =>
    ({
      media: query,
      matches: false,
      onchange: null,
      addEventListener: () => {},
      removeEventListener: () => {},
      addListener: () => {},
      removeListener: () => {},
      dispatchEvent: () => false,
    }) as MediaQueryList;
}
