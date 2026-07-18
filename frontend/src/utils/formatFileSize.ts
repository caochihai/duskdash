/** 1536 -> "1,5 KB" */
export function formatFileSize(bytes: number): string {
  if (bytes <= 0) return '0 B';

  const units = ['B', 'KB', 'MB', 'GB'];
  const exponent = Math.min(Math.floor(Math.log(bytes) / Math.log(1024)), units.length - 1);
  const value = bytes / Math.pow(1024, exponent);
  const decimals = exponent === 0 ? 0 : value >= 10 ? 0 : 1;

  return `${value.toFixed(decimals).replace('.', ',')} ${units[exponent]}`;
}

/** "bao-cao.pdf" -> "PDF" */
export function getFileExtensionLabel(fileName: string): string {
  const dotIndex = fileName.lastIndexOf('.');
  if (dotIndex === -1 || dotIndex === fileName.length - 1) return 'FILE';
  return fileName.slice(dotIndex + 1).toUpperCase();
}
