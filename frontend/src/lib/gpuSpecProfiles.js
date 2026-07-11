export const gpuProfiles = {
  'RTX 5050': { name: 'RTX 5050', architecture: 'Blackwell-class', smCount: 20, cudaCoresPerSm: 128 },
  'RTX 4090': { name: 'RTX 4090', architecture: 'Ada Lovelace', smCount: 128, cudaCoresPerSm: 128 },
  'RTX 3090': { name: 'RTX 3090', architecture: 'Ampere', smCount: 82, cudaCoresPerSm: 128 },
  'A100': { name: 'A100', architecture: 'Ampere', smCount: 108, cudaCoresPerSm: 64 },
  'H100': { name: 'H100', architecture: 'Hopper', smCount: 132, cudaCoresPerSm: 128 },
  'V100': { name: 'V100', architecture: 'Volta', smCount: 80, cudaCoresPerSm: 64 },
  'RTX 2080': { name: 'RTX 2080', architecture: 'Turing', smCount: 46, cudaCoresPerSm: 64 },
};


export const getProfileOptions = () => Object.keys(gpuProfiles);