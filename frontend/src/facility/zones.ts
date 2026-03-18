export interface PanelZone {
  top?: string;
  bottom?: string;
  left?: string;
  right?: string;
  width: string;
  height: string;
}

export type ZoneName = 'wall-display' | 'desk-terminal' | 'readout' | 'main-screen' | 'center-area' | 'left-screen' | 'right-screen' | 'full-screen' | 'ticker';

export const ZONES: Record<ZoneName, PanelZone> = {
  'wall-display':   { top: '8%',  left: '18%', width: '64%', height: '38%' },
  'desk-terminal':  { top: '55%', left: '22%', width: '56%', height: '32%' },
  'readout':        { top: '8%',  right: '5%', width: '12%', height: '6%' },
  'main-screen':    { top: '5%',  left: '8%',  width: '84%', height: '40%' },
  'center-area':    { top: '50%', left: '15%', width: '70%', height: '38%' },
  'left-screen':    { top: '10%', left: '3%',  width: '42%', height: '55%' },
  'right-screen':   { top: '10%', left: '55%', width: '42%', height: '55%' },
  'full-screen':    { top: '5%',  left: '8%',  width: '84%', height: '82%' },
  'ticker':         { bottom: '2%', left: '10%', width: '80%', height: '6%' },
};
