/**
 * High-Reliability Browser WAV Audio Recorder
 * - Uses Web Audio API compatible with all modern browsers
 * - Zeroes out the output buffer directly so speaker feedback is completely muted
 *   WITHOUT triggering Chrome's dead-code node culling
 * - Downsamples to 16,000 Hz 16-bit PCM WAV (Supported by Gnani.ai STT)
 */

export class AudioRecorder {
  constructor() {
    this.audioContext = null;
    this.mediaStream = null;
    this.processor = null;
    this.source = null;
    this.audioData = [];
    this.isRecording = false;
    this.maxAmplitude = 0;
  }

  async start() {
    if (this.isRecording) return;
    this.audioData = [];
    this.maxAmplitude = 0;

    // 1. Immediately create and resume AudioContext on user interaction
    const AudioContextClass = window.AudioContext || window.webkitAudioContext;
    this.audioContext = new AudioContextClass();
    if (this.audioContext.state === "suspended") {
      await this.audioContext.resume();
    }

    // 2. Request microphone stream
    this.mediaStream = await navigator.mediaDevices.getUserMedia({
      audio: {
        channelCount: 1,
        echoCancellation: true,
        noiseSuppression: true,
        autoGainControl: true,
      },
    });

    // Make sure AudioContext is still running after media stream approval
    if (this.audioContext.state === "suspended") {
      await this.audioContext.resume();
    }

    this.source = this.audioContext.createMediaStreamSource(this.mediaStream);

    // Buffer size 4096, 1 input channel, 1 output channel
    this.processor = this.audioContext.createScriptProcessor(4096, 1, 1);

    this.processor.onaudioprocess = (e) => {
      if (!this.isRecording) return;
      const input = e.inputBuffer.getChannelData(0);
      const output = e.outputBuffer.getChannelData(0);

      // CRITICAL: Zero out the output buffer so speaker does NOT emit feedback,
      // but Chrome does NOT cull this node as dead code!
      for (let i = 0; i < output.length; i++) {
        output[i] = 0;
      }

      // Record input samples and track max amplitude
      const chunk = new Float32Array(input.length);
      for (let i = 0; i < input.length; i++) {
        const val = input[i];
        chunk[i] = val;
        const abs = Math.abs(val);
        if (abs > this.maxAmplitude) {
          this.maxAmplitude = abs;
        }
      }

      this.audioData.push(chunk);
    };

    // Connect audio pipeline: source -> processor -> destination
    this.source.connect(this.processor);
    this.processor.connect(this.audioContext.destination);

    this.isRecording = true;
  }

  async stop() {
    if (!this.isRecording) return null;
    this.isRecording = false;

    // Disconnect processor & source
    if (this.processor) {
      try {
        this.processor.disconnect();
      } catch (_) {}
      this.processor = null;
    }

    if (this.source) {
      try {
        this.source.disconnect();
      } catch (_) {}
      this.source = null;
    }

    // Stop mic stream
    if (this.mediaStream) {
      this.mediaStream.getTracks().forEach((track) => track.stop());
      this.mediaStream = null;
    }

    const nativeRate = this.audioContext ? this.audioContext.sampleRate : 44100;

    if (this.audioContext && this.audioContext.state !== "closed") {
      try {
        await this.audioContext.close();
      } catch (_) {}
      this.audioContext = null;
    }

    // Merge audio chunks
    let totalSamples = 0;
    for (const chunk of this.audioData) {
      totalSamples += chunk.length;
    }

    if (totalSamples === 0) {
      return null;
    }

    const merged = new Float32Array(totalSamples);
    let offset = 0;
    for (const chunk of this.audioData) {
      merged.set(chunk, offset);
      offset += chunk.length;
    }

    // Downsample to 16,000 Hz
    const targetSampleRate = 16000;
    const resampled = this.downsampleBuffer(merged, nativeRate, targetSampleRate);

    return this.encodeWav(resampled, targetSampleRate);
  }

  downsampleBuffer(buffer, sampleRate, outSampleRate) {
    if (outSampleRate >= sampleRate) {
      return buffer;
    }

    const ratio = sampleRate / outSampleRate;
    const newLength = Math.round(buffer.length / ratio);
    const result = new Float32Array(newLength);

    let offsetResult = 0;
    let offsetBuffer = 0;

    while (offsetResult < result.length) {
      const nextOffsetBuffer = Math.round((offsetResult + 1) * ratio);
      let accum = 0;
      let count = 0;

      for (let i = offsetBuffer; i < nextOffsetBuffer && i < buffer.length; i++) {
        accum += buffer[i];
        count++;
      }

      result[offsetResult] = count > 0 ? accum / count : 0;
      offsetResult++;
      offsetBuffer = nextOffsetBuffer;
    }

    return result;
  }

  encodeWav(samples, sampleRate) {
    const buffer = new ArrayBuffer(44 + samples.length * 2);
    const view = new DataView(buffer);

    this.writeString(view, 0, "RIFF");
    view.setUint32(4, 36 + samples.length * 2, true);
    this.writeString(view, 8, "WAVE");

    this.writeString(view, 12, "fmt ");
    view.setUint32(16, 16, true);
    view.setUint16(20, 1, true); // PCM
    view.setUint16(22, 1, true); // Mono
    view.setUint32(24, sampleRate, true);
    view.setUint32(28, sampleRate * 2, true);
    view.setUint16(32, 2, true);
    view.setUint16(34, 16, true);

    this.writeString(view, 36, "data");
    view.setUint32(40, samples.length * 2, true);

    let index = 44;
    for (let i = 0; i < samples.length; i++) {
      let s = Math.max(-1, Math.min(1, samples[i]));
      s = s < 0 ? s * 0x8000 : s * 0x7fff;
      view.setInt16(index, s, true);
      index += 2;
    }

    return new Blob([view], { type: "audio/wav" });
  }

  writeString(view, offset, string) {
    for (let i = 0; i < string.length; i++) {
      view.setUint8(offset + i, string.charCodeAt(i));
    }
  }
}
