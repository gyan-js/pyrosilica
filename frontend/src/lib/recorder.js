export class RunRecorder {
  constructor(canvasElement) {
    this.canvas = canvasElement;
    this.mediaRecorder = null;
    this.recordedChunks = [];
    this.totalSize = 0;
  }

 
  startRecording(fps = 120, onSizeUpdate = null) {
    this.recordedChunks = [];
    this.totalSize = 0;
    const stream = this.canvas.captureStream(fps);
    
    const options = { mimeType: 'video/webm; codecs=vp9' };
    
    try {
      this.mediaRecorder = new MediaRecorder(stream, options);
    } catch (e) {
      console.warn('VP9 not supported, falling back to default mimeType');
      this.mediaRecorder = new MediaRecorder(stream);
    }

    this.mediaRecorder.ondataavailable = (event) => {
      if (event.data.size > 0) {
        this.recordedChunks.push(event.data);
        this.totalSize += event.data.size;
       
        if (onSizeUpdate) onSizeUpdate(this.totalSize);
      }
    };

   
    this.mediaRecorder.start(1000);
    console.log(`[Recorder] Started recording run at ${fps} FPS...`);
  }

  stopAndDownload(filename = 'gpu-training-run.webm') {
    if (!this.mediaRecorder || this.mediaRecorder.state === 'inactive') return;

    this.mediaRecorder.onstop = () => {
      const blob = new Blob(this.recordedChunks, { type: 'video/webm' });
      const url = URL.createObjectURL(blob);
      
      const a = document.createElement('a');
      a.style.display = 'none';
      a.href = url;
      a.download = filename;
      document.body.appendChild(a);
      a.click();
      
      setTimeout(() => {
        document.body.removeChild(a);
        URL.revokeObjectURL(url);
      }, 100);
      
      console.log(`[Recorder] Run saved to disk. Total size: ${(this.totalSize / (1024 * 1024)).toFixed(2)} MB`);
    };

    this.mediaRecorder.stop();
  }
}

