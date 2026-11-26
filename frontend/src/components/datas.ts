/**
 * Formatos aceites ao escrever uma data à mão nos calendários (antd): a
 * primeira é a que se mostra; as outras só servem para ler o que se escreve
 * — 01/01/2027, 1/1/2027, 01-01-2027, 01.01.2027 ou 01012027.
 */
export const FORMATO_DATA = ["DD/MM/YYYY", "D/M/YYYY", "DDMMYYYY", "DD-MM-YYYY", "D-M-YYYY", "DD.MM.YYYY", "D.M.YYYY"];

/** O mesmo com hora: 01/01/2027 14:30, 01012027 1430… */
export const FORMATO_DATA_HORA = ["DD/MM/YYYY HH:mm", "D/M/YYYY H:mm", "DDMMYYYY HHmm", "DDMMYYYY HH:mm", "DD-MM-YYYY HH:mm", "DD.MM.YYYY HH:mm"];
