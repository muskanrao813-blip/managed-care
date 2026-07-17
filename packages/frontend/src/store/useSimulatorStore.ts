import { create } from 'zustand';
import type { AllocationResult, HraAnswers } from '@managed-care/shared';

interface SimulatorState {
  currentStep: number;
  patientId: string | null;
  patientForm: {
    name: string;
    age: number;
    gender: 'MALE' | 'FEMALE' | 'OTHER';
    department: string;
    city: string;
  };
  labValues: Record<string, number>;
  hraAnswers: Partial<HraAnswers>;
  engagementScore: number;
  allocation: AllocationResult | null;
  setStep: (step: number) => void;
  setPatientId: (id: string) => void;
  setPatientForm: (form: Partial<SimulatorState['patientForm']>) => void;
  setLabValues: (values: Record<string, number>) => void;
  setHraAnswers: (answers: Partial<HraAnswers>) => void;
  setEngagementScore: (score: number) => void;
  setAllocation: (allocation: AllocationResult) => void;
}

export const useSimulatorStore = create<SimulatorState>((set) => ({
  currentStep: 1,
  patientId: null,
  patientForm: { name: '', age: 35, gender: 'MALE', department: '', city: '' },
  labValues: {},
  hraAnswers: {},
  engagementScore: 50,
  allocation: null,
  setStep: (step) => set({ currentStep: step }),
  setPatientId: (id) => set({ patientId: id }),
  setPatientForm: (form) => set((s) => ({ patientForm: { ...s.patientForm, ...form } })),
  setLabValues: (values) => set({ labValues: values }),
  setHraAnswers: (answers) => set((s) => ({ hraAnswers: { ...s.hraAnswers, ...answers } })),
  setEngagementScore: (score) => set({ engagementScore: score }),
  setAllocation: (allocation) => set({ allocation }),
}));
