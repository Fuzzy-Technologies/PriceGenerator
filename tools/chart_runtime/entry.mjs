// The shipped runtime contains only the financial chart modules used by our adapter.
import * as echarts from 'echarts/core';
import { CandlestickChart, BarChart, LineChart, ScatterChart } from 'echarts/charts';
import { GridComponent, TooltipComponent, LegendComponent, DataZoomComponent,
    ToolboxComponent, GraphicComponent, TitleComponent } from 'echarts/components';
import { CanvasRenderer } from 'echarts/renderers';

echarts.use([CandlestickChart, BarChart, LineChart, ScatterChart, GridComponent,
    TooltipComponent, LegendComponent, DataZoomComponent, ToolboxComponent,
    GraphicComponent, TitleComponent, CanvasRenderer]);

export const init = echarts.init;
export const version = echarts.version;
export const setPlatformAPI = echarts.setPlatformAPI;
