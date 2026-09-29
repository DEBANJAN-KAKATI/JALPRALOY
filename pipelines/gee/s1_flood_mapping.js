// Quick-look Sentinel-1 flood map for one event over Guwahati.
// Paste into https://code.earthengine.google.com and press Run.
// Same method as s1_flood_mapping.py; use this to eyeball thresholds before exporting.

var aoi = ee.Geometry.Rectangle([91.50, 25.95, 92.20, 26.30]); // Kamrup Metropolitan (approx)
var BASELINE = ['2022-01-01', '2022-03-31'];
var EVENT = ['2022-06-14', '2022-06-26'];   // edit to the event you are studying
var DIFF_DB = -3, WATER_DB = -18;

function vv(start, end) {
  return ee.ImageCollection('COPERNICUS/S1_GRD')
    .filterBounds(aoi).filterDate(start, end)
    .filter(ee.Filter.eq('instrumentMode', 'IW'))
    .filter(ee.Filter.listContains('transmitterReceiverPolarisation', 'VV'))
    .select('VV');
}

var before = vv(BASELINE[0], BASELINE[1]).median().focal_median(50, 'circle', 'meters');
var afterCol = vv(EVENT[0], EVENT[1]);
print('Event scenes', afterCol.aggregate_array('system:time_start').map(function (t) {
  return ee.Date(t).format('YYYY-MM-dd HH:mm');
}));
var after = afterCol.min().focal_median(50, 'circle', 'meters');

var occurrence = ee.Image('JRC/GSW1_4/GlobalSurfaceWater').select('occurrence').unmask(0);
var demCol = ee.ImageCollection('COPERNICUS/DEM/GLO30').select('DEM').filterBounds(aoi);
var dem = demCol.mosaic().setDefaultProjection(demCol.first().projection());
var slope = ee.Terrain.slope(dem);
var hand = ee.Image('MERIT/Hydro/v1_0_1').select('hnd');
var valid = occurrence.lt(80).and(slope.lt(5)).and(hand.lt(20));

var flood = after.subtract(before).lt(DIFF_DB).and(after.lt(WATER_DB)).and(valid).selfMask();

Map.centerObject(aoi, 11);
Map.addLayer(before, {min: -25, max: 0}, 'VV baseline', false);
Map.addLayer(after, {min: -25, max: 0}, 'VV event', false);
Map.addLayer(occurrence.gt(80).selfMask(), {palette: ['0000aa']}, 'Permanent water');
Map.addLayer(flood, {palette: ['ff0000']}, 'Flooded (S1 change detection)');

var areaKm2 = flood.multiply(ee.Image.pixelArea()).reduceRegion({
  reducer: ee.Reducer.sum(), geometry: aoi, scale: 30, maxPixels: 1e10
});
print('Flooded area (km²)', ee.Number(areaKm2.get('VV')).divide(1e6));
