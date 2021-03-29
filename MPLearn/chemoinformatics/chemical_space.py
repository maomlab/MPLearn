# -*- tab-width:4;indent-tabs-mode:nil;show-trailing-whitespace:t;rm-trailing-spaces:t -*-
# vi: set ts=2 noet:


from typing import Sequence
import numpy as np
import pandas as pd
import tqdm
import rdkit.Chem
import rdkit.Chem.rdMolDescriptors


# for APDP pairs
from rdkit.Chem.AtomPairs import Pairs
from rdkit.Chem.AtomPairs import Sheridan
from rdkit import DataStructs

def generate_fingerprints_smiles(
        smiles: Sequence[str],
        substance_ids: Sequence[str],
        fingerprint_type: str = 'ECFP4',
        fingerprint_n_bits = 1024,
        verbose = False):
    """
    Generate fingerprints for a set of molecules

    Args:
        smiles: a list of smiles strings
        fingerprint_type: type of fingerprint to represent molecules for comparison
        fingerprint_n_bits: number of bits in the returned fingerprint

    Returns:
        List[Dict[query_id:str, <library_fields>, tanimoto_similarity:float]]
    """
    valid_fingerprint_types = ['ECFP4', 'APDP']
    if fingerprint_type not in valid_fingerprint_types:
        raise ValueError((
            f"Unrecognized fingerprint_type '{fingerprint_type}'. ",
            f"Valid options are [{', '.join(valid_fingerprint_types)}]"))

    if isinstance(smiles, str):
        smiles = [smiles]

    fingerprints = []
    substance_ids_generated = []
    for index, substance_smiles in enumerate(tqdm.tqdm(smiles)):
        try:
            molecule = rdkit.Chem.MolFromSmiles(substance_smiles, sanitize=False)
        except:
            print((
                f"WARNING: RDKit failed to create molecule '{index}' ",
                f"with smiles '{substance_smiles}'; skipping..."))
            continue

        if molecule is None:
            print((
                f"WARNING: RDKit failed to create molecule '{index}' ",
                f"with smiles '{substance_smiles}'; skipping..."))
            continue

        try:
            molecule.UpdatePropertyCache(strict=False)
            molecule = rdkit.Chem.AddHs(molecule, addCoords=True)
            molecule = rdkit.Chem.RemoveHs(molecule) # Also Sanitizes
        except ValueError as e:
            print((
                f"WARNING: {str(e)}. Skipping molecule '{index}' ",
                f"with smiles '{smiles}'."))
            continue

        if fingerprint_type == "ECFP4":
            try:
                fingerprint = rdkit.Chem.rdMolDescriptors.GetMorganFingerprintAsBitVect(
                    mol=molecule, radius=2, nBits=fingerprint_n_bits)

            except:
                print(f"WARNING: Unable to generate fingerprint for library molecule with index {index}")
                continue
            fingerprints.append(fingerprint)
            substance_ids_generated.append(substance_ids[index])

        elif fingerprint_type == "APDP":
            ap_fp = Pairs.GetAtomPairFingerprint(molecule)
            dp_fp = Sheridan.GetBPFingerprint(molecule)
            #ap_fp.GetLength() == 8388608
            #dp_fp.GetLength() == 8388608
            #16777216 = 8388608 + 8388608

            fingerprint = np.zeros(fingerprint_n_bits)
            for i in ap_fp.GetNonzeroElements().keys():
                fingerprint[i % fingerprint_n_bits] = 1
            for i in dp_fp.GetNonzeroElements().keys():
                fingerprint[(i + 8388608) % fingerprint_n_bits] = 1
        else:
            print(f"ERROR: Unrecognized fingerprint type '{fingerprint_type}'")
            exit(1)

        fingerprints.append(fingerprint)
        substance_ids_generated.append(substance_ids[index])

    fingerprints = np.array(fingerprints)
    return substance_ids_generated, fingerprints

# needs some debugging
def generate_fingerprints_sdf(
        library_path: str,
        library_fields: Sequence[str],
        fingerprint_type: str = 'ECFP4',
        verbose=False):

    """
    Generate fingerprints for substances in the library

    Args:
        libray: path to library .sdf file
        library_fields: fields in the library .sdf file to be reported in the results
        fingerprint_type: type of fingerprint to represent molecules for comparison

    Returns:
        List[Dict[query_id:str, <library_fields>, tanimoto_similarity:float]]
    """

    # validate inputs
    if not os.path.exists(library_path):
        raise ValueError(f"The library path '{library_path}' does not exist.")

    valid_fingerprint_types = ['ECFP4']
    if fingerprint_type not in valid_fingerprint_types:
        raise ValueError((
            f"Unrecognized fingerprint_type '{fingerprint_type}'. ",
            f"Valid options are [{', '.join(valid_fingerprint_types)}]"))

    substances = []
    fingerprints = []
    for library_substance_index, library_substance in enumerate(rdkit.Chem.SDMolSupplier(library_path)):
        if fingerprint_type == "ECFP4":
            try:
                library_fingerprint = rdkit.Chem.rdMolDescriptors.GetMorganFingerprintAsBitVect(
                    mol=library_substance, radius=2, nBits=1024)
            except:
                print(f"WARNING: Unable to generate fingerprint for library molecule with index {library_substance_index}")
                continue


        substance_info = {}
        if library_fields is None:
            substance_info.update(library_substance.GetPropsAsDict())
        else:
            for library_field in library_fields:
                try:
                    library_field_value = library_substance.GetProp(library_field)
                    substance_info[library_field] = library_field_value
                except:
                    print(
                        f"WARNING: Library compound at index {library_substance_index} does not have field {library_field}.")
                    substance_info[library_field] = None
        substance_info["fingerprint"] = library_fingerprint
        substance_info.append(result)

    if verbose:
        print(f"Found library contains {len(results)} substances.")

    fingerprint = np.stack(fingerprints)
    substances = pd.DataFrame(substances)

    return fingerprints, substances
