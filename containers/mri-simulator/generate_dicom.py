#!/usr/bin/env python3
import argparse, os, numpy as np
import pydicom
from pydicom.dataset import Dataset, FileDataset
from pydicom.uid import generate_uid
from datetime import datetime

def generate_dicom_files(count, output_dir, modality, patients):
    os.makedirs(output_dir, exist_ok=True)
    patient_ids = [f"PAT{i:04d}" for i in range(patients)]
    for i in range(count):
        patient_id = patient_ids[i % len(patient_ids)]
        ds = Dataset()
        ds.file_meta = Dataset()
        ds.file_meta.MediaStorageSOPClassUID = '1.2.840.10008.5.1.4.1.1.2'
        ds.file_meta.MediaStorageSOPInstanceUID = generate_uid()
        ds.file_meta.TransferSyntaxUID = '1.2.840.10008.1.2.1'
        ds.PatientName = f"Test^{patient_id}"
        ds.PatientID = patient_id
        ds.Modality = modality
        ds.StudyDate = datetime.now().strftime('%Y%m%d')
        ds.StudyTime = datetime.now().strftime('%H%M%S')
        ds.SOPClassUID = '1.2.840.10008.5.1.4.1.1.2'
        ds.SOPInstanceUID = generate_uid()
        ds.Rows = 64
        ds.Columns = 64
        ds.PixelSpacing = [1.0, 1.0]
        ds.BitsAllocated = 16
        ds.BitsStored = 16
        ds.HighBit = 15
        ds.PixelRepresentation = 0
        ds.SamplesPerPixel = 1
        ds.PhotometricInterpretation = 'MONOCHROME2'
        ds.PixelData = np.random.randint(
            0, 1000, (64, 64), dtype=np.uint16).tobytes()
        fname = os.path.join(
            output_dir, f"{modality}_{patient_id}_{i:04d}.dcm")
        pydicom.dcmwrite(fname, ds)
        print(f"Generated: {fname}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--count",    type=int, default=5)
    parser.add_argument("--output",   default="/opt/dicom_test")
    parser.add_argument("--modality", default="MR")
    parser.add_argument("--patients", type=int, default=3)
    args = parser.parse_args()
    generate_dicom_files(
        args.count, args.output, args.modality, args.patients)
