#!/usr/bin/env python3
"""
generate_dicom.py — Synthetic DICOM test file generator for DIC SOC Lab
Produces realistic-looking DICOM CT/MR files using pydicom.
"""
import argparse
import os
import sys
import random
import struct
from datetime import datetime, timedelta

try:
    import pydicom
    from pydicom.dataset import Dataset, FileDataset
    from pydicom.sequence import Sequence
    from pydicom.uid import generate_uid, ExplicitVRLittleEndian
    import numpy as np
    HAS_PYDICOM = True
except ImportError:
    HAS_PYDICOM = False

PATIENT_NAMES = [
    "Smith^John^A", "Johnson^Mary^B", "Williams^Robert^C",
    "Brown^Linda^D",  "Jones^Michael^E", "Garcia^Patricia^F",
    "Miller^David^G", "Davis^Barbara^H", "Wilson^James^I",
    "Martinez^Susan^J", "Anderson^Richard^K", "Taylor^Dorothy^L",
    "Thomas^Joseph^M", "Jackson^Lisa^N",  "White^Charles^O",
    "Harris^Nancy^P",  "Martin^Mark^Q",   "Thompson^Karen^R",
    "Moore^Paul^S",    "Walker^Betty^T",
]

MODALITY_SOP_CLASSES = {
    "CT": "1.2.840.10008.5.1.4.1.1.2",       # CT Image Storage
    "MR": "1.2.840.10008.5.1.4.1.1.4",       # MR Image Storage
    "CR": "1.2.840.10008.5.1.4.1.1.1",       # CR Image Storage
    "DX": "1.2.840.10008.5.1.4.1.1.1.1",     # Digital X-Ray
}

STUDY_DESCRIPTIONS = {
    "CT": ["CT Chest w/o contrast", "CT Abdomen Pelvis", "CT Head w/o",
           "CT Angiography Chest", "CT Spine Lumbar"],
    "MR": ["MRI Brain w/o contrast", "MRI Lumbar Spine", "MRI Knee",
           "MRI Abdomen w/wo", "MRI Pelvis"],
    "CR": ["Chest PA and Lateral", "Left Hand 3-views", "Pelvis AP"],
    "DX": ["Chest 2-view", "Abdomen supine", "Foot 3-views"],
}


def make_dicom_file(patient_idx: int, study_uid: str, series_uid: str,
                    instance_num: int, modality: str, output_dir: str) -> str:
    """Create a single synthetic DICOM file."""
    if not HAS_PYDICOM:
        # Fallback: write minimal DICOM preamble manually
        filename = os.path.join(output_dir, f"scan_{patient_idx:03d}_{instance_num:04d}.dcm")
        with open(filename, "wb") as f:
            f.write(b"\x00" * 128)  # preamble
            f.write(b"DICM")         # magic bytes
        return filename

    sop_class = MODALITY_SOP_CLASSES.get(modality, MODALITY_SOP_CLASSES["CT"])
    sop_instance_uid = generate_uid()

    # File meta dataset
    file_meta = Dataset()
    file_meta.MediaStorageSOPClassUID    = sop_class
    file_meta.MediaStorageSOPInstanceUID = sop_instance_uid
    file_meta.TransferSyntaxUID          = ExplicitVRLittleEndian
    file_meta.ImplementationClassUID     = generate_uid()
    file_meta.ImplementationVersionName  = "DIC-SOC-LAB-1.0"

    ds = FileDataset(None, {}, file_meta=file_meta, preamble=b"\x00" * 128)
    ds.is_implicit_VR   = False
    ds.is_little_endian = True

    # Study date/time (random within past 30 days)
    study_dt = datetime.now() - timedelta(days=random.randint(0, 30),
                                          hours=random.randint(7, 18))
    ds.StudyDate            = study_dt.strftime("%Y%m%d")
    ds.StudyTime            = study_dt.strftime("%H%M%S")
    ds.SeriesDate           = ds.StudyDate
    ds.SeriesTime           = ds.StudyTime
    ds.ContentDate          = ds.StudyDate
    ds.ContentTime          = ds.StudyTime
    ds.AccessionNumber      = f"ACC{patient_idx:06d}"
    ds.Modality             = modality
    ds.Manufacturer         = "DIC-SOC-LAB"
    ds.InstitutionName      = "Diagnostic Imaging Center"
    ds.ReferringPhysicianName = "Referring^Physician"
    ds.StudyDescription     = random.choice(STUDY_DESCRIPTIONS.get(modality, ["General Study"]))

    # Patient
    ds.PatientName    = PATIENT_NAMES[patient_idx % len(PATIENT_NAMES)]
    ds.PatientID      = f"DIC{patient_idx:06d}"
    ds.PatientBirthDate = f"{random.randint(1940, 2000)}{random.randint(1,12):02d}{random.randint(1,28):02d}"
    ds.PatientSex     = random.choice(["M", "F"])

    # UIDs
    ds.StudyInstanceUID  = study_uid
    ds.SeriesInstanceUID = series_uid
    ds.SOPClassUID       = sop_class
    ds.SOPInstanceUID    = sop_instance_uid

    ds.SeriesNumber      = "1"
    ds.InstanceNumber    = str(instance_num)

    # Image geometry
    rows, cols = 512, 512
    ds.Rows             = rows
    ds.Columns          = cols
    ds.SamplesPerPixel  = 1
    ds.PhotometricInterpretation = "MONOCHROME2"
    ds.BitsAllocated    = 16
    ds.BitsStored       = 12
    ds.HighBit          = 11
    ds.PixelRepresentation = 0
    ds.RescaleIntercept = -1024
    ds.RescaleSlope     = 1.0
    ds.PixelSpacing     = [0.703125, 0.703125]
    ds.SliceThickness   = 2.5
    ds.ImagePositionPatient   = [0.0, 0.0, float(instance_num * 2.5)]
    ds.ImageOrientationPatient = [1.0, 0.0, 0.0, 0.0, 1.0, 0.0]

    # Pixel data — simulate body cross-section (simplified)
    pixel_array = np.zeros((rows, cols), dtype=np.uint16)
    # Background (air) = 0 HU + 1024 offset → ~200
    pixel_array[:] = 200
    # Soft tissue region (center ellipse)
    cy, cx = rows // 2, cols // 2
    for y in range(rows):
        for x in range(cols):
            # Fast approximation using slices
            pass
    # Use faster vectorised approach
    Y, X = np.ogrid[:rows, :cols]
    body_mask  = ((Y - cy)**2 / (cy * 0.9)**2 + (X - cx)**2 / (cx * 0.85)**2) <= 1
    bone_mask  = ((Y - cy)**2 / (cy * 0.15)**2 + (X - cx)**2 / (cx * 0.45)**2) <= 1
    lung_mask_l = ((Y - cy)**2 / (cy * 0.4)**2 + (X - (cx - 80))**2 / (60**2)) <= 1
    lung_mask_r = ((Y - cy)**2 / (cy * 0.4)**2 + (X - (cx + 80))**2 / (60**2)) <= 1

    pixel_array[body_mask]  = np.random.randint(1050, 1120, np.sum(body_mask)).astype(np.uint16)
    pixel_array[bone_mask]  = np.random.randint(1400, 1900, np.sum(bone_mask)).astype(np.uint16)
    pixel_array[lung_mask_l] = np.random.randint(100, 200,  np.sum(lung_mask_l)).astype(np.uint16)
    pixel_array[lung_mask_r] = np.random.randint(100, 200,  np.sum(lung_mask_r)).astype(np.uint16)

    ds.PixelData = pixel_array.tobytes()

    filename = os.path.join(output_dir,
                            f"{modality.lower()}_patient{patient_idx:03d}_i{instance_num:04d}.dcm")
    pydicom.dcmwrite(filename, ds)
    return filename


def main():
    parser = argparse.ArgumentParser(description="Generate synthetic DICOM files")
    parser.add_argument("--count",    type=int, default=20,      help="Number of files")
    parser.add_argument("--output",   type=str, default="/opt/dicom_test")
    parser.add_argument("--modality", type=str, default="CT", choices=["CT", "MR", "CR", "DX"])
    parser.add_argument("--patients", type=int, default=5,       help="Number of unique patients")
    args = parser.parse_args()

    os.makedirs(args.output, exist_ok=True)

    print(f"[DICOM-GEN] Generating {args.count} {args.modality} DICOM files in {args.output}")

    if not HAS_PYDICOM:
        print("[DICOM-GEN] pydicom not found — creating minimal placeholder files")

    files_per_patient = max(1, args.count // args.patients)
    created = 0

    for p in range(args.patients):
        study_uid  = generate_uid() if HAS_PYDICOM else f"1.2.3.{p}"
        series_uid = generate_uid() if HAS_PYDICOM else f"1.2.3.{p}.1"
        for i in range(1, files_per_patient + 1):
            if created >= args.count:
                break
            fname = make_dicom_file(p, study_uid, series_uid, i, args.modality, args.output)
            created += 1
            print(f"[DICOM-GEN]   Created: {os.path.basename(fname)}")

    # Fill remainder
    while created < args.count:
        study_uid  = generate_uid() if HAS_PYDICOM else f"1.2.3.99.{created}"
        series_uid = generate_uid() if HAS_PYDICOM else f"1.2.3.99.{created}.1"
        fname = make_dicom_file(created % args.patients, study_uid, series_uid,
                                created, args.modality, args.output)
        created += 1
        print(f"[DICOM-GEN]   Created: {os.path.basename(fname)}")

    total_size = sum(
        os.path.getsize(os.path.join(args.output, f))
        for f in os.listdir(args.output)
        if f.endswith(".dcm")
    )
    print(f"\n[DICOM-GEN] Done. {created} files created. "
          f"Total size: {total_size / (1024*1024):.1f} MB")


if __name__ == "__main__":
    main()
