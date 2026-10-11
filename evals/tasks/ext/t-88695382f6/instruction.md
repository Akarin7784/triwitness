Add a command line option to have job launching sleep between steps
To give a distributed filesystem time to settle. Without this it appears that a job may be launched even when `sbatch` is run with a dependency if the dependent job is not yet apparent (due to filesystem consistency slowness).
