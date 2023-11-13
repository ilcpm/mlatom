#!/usr/bin/env python3
'''
.. code-block::

  !---------------------------------------------------------------------------! 
  ! dftd4: interface to the dftd4 program                                     ! 
  ! Implementations by: Pavlo O. Dral & Peikun Zheng                          !
  !---------------------------------------------------------------------------! 
'''
import json
import numpy as np
import sys
from .. import data
from .. import models
from .. import stopper
from .. import environment_variables
from ..utils import doc_inherit

class dftd4_methods(models.model):
    '''
    DFT-D4 interface

    Arguments:
        functional (str): functional to use
    
    .. note::
    
        The default DFT-D4 implementation provides a shared memory parallelisation for CPUs. 
        They offer openMP parallelisation, which is not implemented here currently. 
        For more discussion, please refer to  https://github.com/dftd4/dftd4/issues/20.

    '''
    def __init__(self, functional=None, save_files_in_current_directory=True, **kwargs):
        self.functional = functional
        self.save_files_in_current_directory = save_files_in_current_directory
        if 'nthreads' in kwargs:
            self.nthreads = kwargs['nthreads']
        else:
            self.nthreads = environment_variables.env.get_nthreads()
    
    @doc_inherit
    def predict(self, molecular_database=None, molecule=None,
                calculate_energy=True, calculate_energy_gradients=False, calculate_hessian=False):
        molDB = super().predict(molecular_database=molecular_database, molecule=molecule)

        environment_variables.env.set_nthreads(self.nthreads)
        import os
        try: dftd4bin = os.environ['dftd4bin']
        except:
            raise ValueError('Cannot find the dftd4bin program, please set the environment variable: export dftd4bin=...')
        
        if calculate_energy_gradients or calculate_hessian:
            try:
                from .. import constants
            except:
                import constants
            
        import tempfile, subprocess        
        ii = 0
        for mol in molDB.molecules:
            with tempfile.TemporaryDirectory() as tmpdirname:
                if self.save_files_in_current_directory: tmpdirname='.'
                ii += 1
                xyzfilename = f'{tmpdirname}/predict{ii}.xyz'
                mol.write_file_with_xyz_coordinates(filename = xyzfilename)
                
                dftd4args = [dftd4bin, xyzfilename, '-f', '%s' % self.functional, '-c', '%d' % mol.charge, '-s', '-s', '--noedisp']
                if calculate_hessian:
                    dftd4args += ['--json', '--grad', '--hessian']
                elif calculate_energy_gradients:
                    dftd4args += ['--json', '--grad']
                elif calculate_energy:
                    dftd4args += ['--json']
                dftd4outfilename = f'{tmpdirname}/mndo{ii}.out'
                # dftd4args += ['&>',dftd4outfilename]
                # cmd = ' '.join(dftd4args)
                # proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, cwd=tmpdirname, universal_newlines=True,shell=True)
                # proc.wait()
                # dftd4_successful = False
                # with open(dftd4outfilename,'r') as fout:
                #     for readable in fout:
                #         if 'normal termination of dftd4' in readable:
                #             dftd4_successful = True
                proc = subprocess.Popen(dftd4args, stdout=subprocess.PIPE, stderr=subprocess.PIPE, cwd=tmpdirname, universal_newlines=True)
                outs,errs = proc.communicate() # Type of outs and errs is str
                #print(outs.split('\n'))
                dftd4_successful = False
                if 'Error termination' not in outs+errs:
                    dftd4_successful = True

                mol.dftd4_successful = dftd4_successful
                with open(f'{tmpdirname}/dftd4.json', 'r') as f:
                    d4_results = json.load(f)
                
                if calculate_energy:
                    energy = float(d4_results['energy'])
                    mol.energy = energy
                if calculate_energy_gradients:
                    grad = np.array(d4_results['gradient']) / constants.Bohr2Angstrom
                    grad = grad.reshape(-1, 3)
                    for iatom in range(len(mol.atoms)):
                        mol.atoms[iatom].energy_gradients = grad[iatom]
                if calculate_hessian:
                    natoms = len(mol.atoms)
                    hess = np.array(d4_results['hessian']) / (constants.Bohr2Angstrom**2)
                    mol.hessian = hess.reshape(natoms*3,natoms*3)

if __name__ == '__main__':
    pass
