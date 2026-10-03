'use strict';

(function attachRequestGate(root) {
  class RequestGate {
    constructor() {
      this.generation = 0;
      this.controller = null;
    }

    invalidate() {
      this.generation += 1;
      if (this.controller) this.controller.abort();
      this.controller = null;
      return this.generation;
    }

    begin() {
      this.generation += 1;
      if (this.controller) this.controller.abort();
      this.controller = new AbortController();
      return { generation: this.generation, signal: this.controller.signal };
    }

    isCurrent(generation) {
      return generation === this.generation;
    }

    finish(generation) {
      if (!this.isCurrent(generation)) return false;
      this.controller = null;
      return true;
    }
  }

  root.ClassShiftRequestGate = RequestGate;
})(globalThis);
