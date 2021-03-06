import numpy as np
import pandas as pd
import glob
import math
import os.path
from scipy import interpolate
import datetime as dt
from datetime import datetime,timedelta
from mpl_toolkits.basemap import Basemap
from matplotlib.mlab import griddata
from matplotlib.ticker import MultipleLocator
from scipy import interpolate
import csv
import matplotlib.pyplot as plt
import pickle
from sklearn import linear_model
from sklearn.metrics import mean_absolute_error,explained_variance_score
from sklearn.preprocessing import PolynomialFeatures
from sklearn.pipeline import make_pipeline
from mpl_toolkits.axes_grid.inset_locator import inset_axes
import matplotlib.dates as mdates
from matplotlib.patches import Polygon


#Takes in a set of desired attributes, the species, and the year range
#returns an observation x [lat, lon, season, attribute_1, attribute_2,...attribute_n] matrix 
def load_observations(config):
	path = os.path.normpath('Birdgriddata') 
	allFiles = glob.glob(path + "/*.csv")
	observations = pd.DataFrame()
	ColumnNames=np.append(config["ATTRIBUTES"],config['SPECIES'])
	list_ = []
	for file_ in allFiles:
		df = pd.read_csv(file_,index_col=None,header=0,usecols=ColumnNames)
		list_.append(df)
	observations= pd.concat(list_)
	observations=observations[(observations['YEAR']>=config['START_YEAR']-1)&(observations['YEAR']<=config['END_YEAR'])]
	observations=observations.replace('X',1) 
	observations=observations.replace('?',0)
	return observations

#Takes in the matrix of observations and bins it into observations based on the provided grid size.
#Returns an array of dicts, each dict represents one location and contains lat, lon and data for each timestep
#Returns a dataframe of attributes that are divided into grids, where as each grid square represents the total count of the species found in that location

def init_birdgrid(observations,config,SEASONS):
	lats=observations['LATITUDE']
	lons=observations['LONGITUDE']
	observations=observations.convert_objects(convert_numeric=True)
	lat_min = int(math.floor(min(lats)))
	lat_max = int(math.floor(max(lats)))
	lon_min =int(math.floor(min(lons)))
	lon_max =int(math.floor(max(lons)))
	GridSquare=[]
	df=pd.DataFrame([])
	nw=pd.DataFrame([])
	dataframe_remove=pd.DataFrame([])
	
	if config["TIME_STEP"] =='monthly':
		for i in range(lat_min,lat_max,config['GRID_SIZE']):
			for j in range(lon_min,lon_max,config['GRID_SIZE']):
				GridSquare=observations[(observations['LATITUDE']>=i)&(observations['LATITUDE']<i+config['GRID_SIZE'])&(observations['LONGITUDE']>=j)&(observations['LONGITUDE']<j+config['GRID_SIZE'])]
				GridSquare['LATITUDE']=i
				GridSquare['LONGITUDE']=j
				if config['use_chance_not_count']:
					counts={}
					counts['LATITUDE']=[]
					counts['LONGITUDE'] =[]
					counts['YEAR']=[]
					counts['MONTH']=[]
					counts[config['SPECIES']]=[]
					for (lat,lon,y,m),g in GridSquare.groupby(['LATITUDE','LONGITUDE','YEAR','MONTH'],as_index=False):
						counts['LATITUDE'].append(lat)
						counts['LONGITUDE'].append(lon)
						counts['YEAR'].append(y)
						counts['MONTH'].append(m)
						counts[config['SPECIES']].append(float(np.sum(g[config['SPECIES']].values>0))/g.shape[0])      #Changing the frequency values with the chance for each gridsquare
					GridwiseCount = pd.DataFrame.from_dict(counts)
				else:
					GridwiseCount=GridSquare.groupby(['LATITUDE','LONGITUDE','YEAR','MONTH'],as_index=False)[config['SPECIES']].sum()
				
				df=df.append(GridwiseCount)
		monthnumber=0
		for year in range(config['START_YEAR']-1,config['END_YEAR']+1):
			for month in range(1,13):
				obs=df[(df['YEAR']==year)&(df['MONTH']==month)]
				obs['timeframe']=monthnumber						# Adding a new dataframe column 'timeframe' as month intervals
				nw=nw.append(obs)
				monthnumber += 1
	elif config["TIME_STEP"] == "weekly":
		raise NotImplementedError
	nw=nw.reset_index()
	nw['Date_Format']=pd.Series("-".join(a) for a in zip(nw.YEAR.astype("int").astype(str),nw.MONTH.astype("int").astype(str)))
	
	for k,location in nw.groupby(['LATITUDE','LONGITUDE'],as_index=False):
		for year in range(config['START_YEAR']-1,config['END_YEAR']+1):
			for season in SEASONS:
				eachgrid_data=(location.loc[location['YEAR']==year])
				months_count=len(eachgrid_data.loc[eachgrid_data['MONTH'].isin(SEASONS[season])])
				if months_count < 3:
					dataframe_remove=dataframe_remove.append(location)     # revoming the grid which doesn't have 3 data points in a season
					continue
	updated_dataframe = nw[~nw.index.isin(dataframe_remove.index)]	
	updated_dataframe.to_pickle(config["RUN_NAME"]+"_locations.p")
	return updated_dataframe

#Plot the actual species frequency (from the data) on a map
def plot_observation_frequency(locations,SEASONS,config):
	for year in range(config['START_YEAR'],config['END_YEAR']+1):
		for season in SEASONS:
			wanted=SEASONS[season]
			latitude = np.asarray(locations['LATITUDE'])
			longitude = np.asarray(locations['LONGITUDE'])
			Yearly_Data=(locations.loc[locations['YEAR']==year])
			Seasonal_Data=(Yearly_Data.loc[Yearly_Data['MONTH'].isin(wanted)])
			lats = np.asarray(Seasonal_Data['LATITUDE'])
			lons = np.asarray(Seasonal_Data['LONGITUDE'])
			Species_count=np.asarray(Seasonal_Data[config['SPECIES']])
			Species_count=np.reshape(Species_count,len(Species_count))
			lat_min = min(lats)
			lat_max = max(lats)
			lon_min = min(lons)
			lon_max = max(lons)
			spatial_resolution = 1 
			fig = plt.figure()
			x = np.array(lons)
			y = np.array(lats)
			z = np.array(Species_count)
			xinum = (lon_max - lon_min) / spatial_resolution
			yinum = (lat_max - lat_min) / spatial_resolution
			xi = np.linspace(lon_min, lon_max + spatial_resolution, xinum)        
			yi = np.linspace(lat_min, lat_max + spatial_resolution, yinum)        
			xi, yi = np.meshgrid(xi, yi)
			zi = griddata(x, y, z, xi, yi, interp='linear')
			m = Basemap(projection = 'merc',llcrnrlat=lat_min, urcrnrlat=lat_max,llcrnrlon=lon_min, urcrnrlon=lon_max,rsphere=6371200., resolution='l', area_thresh=10000)
			m.drawcoastlines()
			m.drawstates()
			m.drawcountries()
			m.drawparallels(np.arange(lat_min,lat_max,config['GRID_SIZE']),labels=[False,True,True,False])
			m.drawmeridians(np.arange(lon_min,lon_max,config['GRID_SIZE']),labels=[True,False,False,True])
			lat, lon = m.makegrid(zi.shape[1], zi.shape[0])
			x,y = m(lat, lon)
			z=zi.reshape(xi.shape)
			levels=np.linspace(0,z.max(),25)
			cm=plt.contourf(x, y, zi,levels=levels,cmap=plt.cm.Greys)
			plt.colorbar()
			plt.title(config['SPECIES']+"-"+str(year)+"-"+str(season))
			#plt.show()
			plt.savefig(config['SPECIES']+"-"+str(year)+"-"+str(season)+".png")
			plt.close()
	return

#Plots the frequency (Y axis) against the timesteps (X axis) for the given location.
#Uses the location's included coordinates to provide a map insert showing a dot for the location on the US map (this should use matplotlib's "axes" interface as with here http://matplotlib.org/examples/pylab_examples/axes_demo.html)
#The optional "predictor" object overlays the expectations of a particular predictor (which is associated with a particular timestamp)


def model_location_novelty_over_time(location,SEASONS,config):
	ModelObject=[]
	Maximum_Error=[]
	Mean_Error=[]
	mean_abs_errors = []
	explained_var = []
	Regression_Coefficient=[]
	Regression_Intercepts=[]
	Regression_Score=[]
	Predictions=[]
	seasonlist=[]
	predictingyearlist=[]
	latitude=[]
	longitude=[]
	NonSeasonalData_TrainData=[]
	Season_TrainData=[]
	Season_TestData=[]
	NonSeasonalData_TestData=[]
	Winter_startyear_Data=[]
	tr= pd.DataFrame()
	tr1=pd.DataFrame()
	LocationData = location
	d={}
	
	for predictingyear in range(config['PREDICTION_START_YEAR'],config['END_YEAR']+1):
		predicting_year=[predictingyear]
		Training_years=[]
		for year in range(config['START_YEAR'],predictingyear,1):
			Training_years.append(year)
		for season in SEASONS:
			wanted=SEASONS[season]
			NonSeasonal_Data=(LocationData.loc[~LocationData['MONTH'].isin(wanted)])    #selecting the data that doesn't belong to the required season as NonSeasonal_Data
			NonSeasonalData=(NonSeasonal_Data.loc[NonSeasonal_Data['YEAR'].isin(Training_years)])
			#NonSeasonalData=NonSeasonalData.append(NonSeasonal_Data[NonSeasonal_Data['YEAR']==predicting_year],ignore_index=True)
			Seasonal_Data=LocationData[LocationData['MONTH'].isin(wanted)]            #selecting the required seasonal data as Seasonal_Data
			Train_Data=Seasonal_Data[Seasonal_Data['YEAR'].isin(Training_years)]      #selecting the data that belongs to training_years from Seasonal_Data as Train_Data
			max_train_year=max(Training_years)
			min_train_year=min(Training_years)
			NonSeasonal_TestData=(NonSeasonal_Data.loc[NonSeasonal_Data['YEAR'].isin(predicting_year)])	#Selecting the predicting_year data from NonSeasonal_Data
			Test_Data=(Seasonal_Data.loc[Seasonal_Data['YEAR'].isin(predicting_year)])                  #considering the predicting_year data from Seasonal_Data as Test_Data
			NonSeasonaltimeframe_TestData=NonSeasonaltimeframe_TestData.reshape(-1,1)
			if season =='Winter':                                                                       # For winter season considering the 12th month data point of the Maximum Train data year into Test_Data  
				Test_Data=Test_Data[(Test_Data['YEAR']==predicting_year)&(Test_Data['MONTH']!=12)]
				Test_Data=Test_Data.append(Train_Data[(Train_Data['YEAR']==max_train_year)&(Train_Data['MONTH']==12)], ignore_index=True)
				tr=Train_Data[(Train_Data['YEAR']!=max_train_year)]
				Train_Data=tr.append(Train_Data[(Train_Data['YEAR']==max_train_year)&(Train_Data['MONTH']!=12)],ignore_index=True)
				#Train_Data=Train_Data.append(Train_Data[(Train_Data['YEAR']==max_train_year)&(Train_Data['MONTH']!=12)],ignore_index=True)
				if min_train_year >=2003:
					Starting_yearData=LocationData[LocationData['MONTH'].isin(SEASONS['Winter'])]
					Train_Data=Train_Data.append(Starting_yearData[(Starting_yearData['YEAR']==min_train_year-1)&(Starting_yearData['MONTH']==12)],ignore_index=True)
			
			Winter_previousyear_Data=pd.DataFrame()
			for year in range(min_train_year,max_train_year+2):
				tr1=LocationData[(LocationData['YEAR']==year-1)&(LocationData['MONTH']==11)]
				Winter_previousyear_Data=Winter_previousyear_Data.append(tr1)	
			
			TrainData_Months=Train_Data['timeframe']										#Considering timeframe as TrainData_Months
			TrainData_Months=TrainData_Months.reshape(-1,1)                                       #reshaping Train_Data to fit into model
			Seasonwise_TrainData=Train_Data['Date_Format']							
			Seasonwise_Traindata_Frequency=Train_Data[config['SPECIES']]
			TrainData_Frequency = Seasonwise_Traindata_Frequency.as_matrix()
			TrainData_Frequency=TrainData_Frequency.astype(np.float)                      #Considering species count/chance as the target value of Train_Data
			TestData_Months=Test_Data['timeframe']                                        
			TestData_Months=TestData_Months.reshape(-1,1)
			TestData_Plotting=Test_Data['Date_Format']
			Actual_Species_Count=Test_Data[config['SPECIES']]
			lat=Test_Data['LATITUDE']
			lon=Test_Data['LONGITUDE']
			
			if len(Train_Data)!=0 and len(TestData_Months)!=0:
				if config['PREDICTOR']=='linear':
					regr = linear_model.LinearRegression()                          #Building LinearRegression model object if the config['PREDICTOR'] value is 'linear'
				elif config['PREDICTOR']=='theilsen':
					regr = linear_model.TheilSenRegressor()                         #Building TheilSenRegression if the config['PREDICTOR'] value is 'theilsen'
				regr.fit(TrainData_Months,TrainData_Frequency)
				Predicted_Species_Count=regr.predict(TestData_Months)                      #Predicting the species count/chance 
				MaxError=np.max(abs(Predicted_Species_Count-Actual_Species_Count))  #Finding the maximum absolute error by comparing predicted values with that of the true values
				Maximum_Error.append(MaxError)
				MeanError=np.mean((Predicted_Species_Count - Actual_Species_Count) ** 2)  #Finding the mean squared error
				Mean_Error.append(MeanError)                                         # Appending the meanerror of every season through every predicting year of a particular location
				r2_test=regr.score(TestData_Months,Actual_Species_Count)                    
				r2_train=regr.score(TrainData_Months,TrainData_Frequency)
				mae_test = mean_absolute_error(Actual_Species_Count,Predicted_Species_Count)
				mae_train = mean_absolute_error(TrainData_Frequency,regr.predict(TrainData_Months))
				e_v = explained_variance_score(TrainData_Frequency,regr.predict(TrainData_Months))
				explained_var.append(e_v)
				Regression_Score.append((r2_train,r2_test))
				mean_abs_errors.append((mae_train,mae_test))                           # Appending the mean absolute error of every season through every predicting year of a particular location
				seasonlist.append(season)
				predictingyearlist.append(predicting_year)
				latitude.append(lat)
				longitude.append(lon)
				ModelObject.append(regr)
				Predictions.append(Predicted_Species_Count)
				NonSeasonalData_TrainData.append(NonSeasonalData)
				Season_TrainData.append(Train_Data)
				Season_TestData.append(Test_Data)
				NonSeasonalData_TestData.append(NonSeasonal_TestData)
				Winter_startyear_Data.append(Winter_previousyear_Data)
			else:
				continue
			
	d['location']={}                                                                #Creating a dictionary 
	d['stats']={}
	d['location']['latitude']=latitude
	d['location']['longitude']=longitude
	d['stats']['score']=Regression_Score
	d['stats']['max_error']=np.reshape(Maximum_Error, len(Maximum_Error))
	d['stats']['mean_error']=np.reshape(Mean_Error, len(Mean_Error))
	d["stats"]["mean_abs_errors"] = mean_abs_errors
	d["stats"]["expvar"] = explained_var
	d['predictions']=Predictions
	d['seasonlist']=seasonlist
	d['predictingyearlist']=np.reshape(predictingyearlist,len(predictingyearlist))
	d['Model_object']=ModelObject
	d['Nonseasonal_TrainData']=NonSeasonalData_TrainData
	d['TrainData']=Season_TrainData
	d['TestData']=Season_TestData
	d['NonSeasonalData_TestData']=NonSeasonalData_TestData
	d['Winter_startyear_Data']=Winter_startyear_Data
	return d


def plot_birds_over_time(predictors,locations,config):
	lat_list=[]
	lon_list=[]
	for q in predictors:
		for total_latitudes,total_longitudes in zip(q["location"]["latitude"],q["location"]["longitude"]):
			lat_list.append(total_latitudes.values[0])
			lon_list.append(total_longitudes.values[0])
	lat_min=min(lat_list)
	lat_max = max(lat_list)
	lon_min = min(lon_list)
	lon_max = max(lon_list)	
	if config['use_chance_not_count']:
		SeasonTrainData_Label="Sighting chance (months)"
		TestData_Label="Sighting chance( )"
		NonSeasonalData_Label="Sighting chance (all months)" 
		RegressorLine_Label="Expected sighting chance"
		YAxis_Label="Chance to see (%)"
	else:
		SeasonTrainData_Label="Sightings( months)"
		TestData_Label="Sightings( )"
		NonSeasonalData_Label="Sightings(all months)"
		RegressorLine_Label="Expected sightings"
		YAxis_Label="Number of sightings"
	
	for regline in config['REGRESSION_LINE']:
		for p in predictors:
			for Model_Object,Predictions,latitude,longitude,season,predicting_year,Nonseasonal_TrainData,TrainData,TestData,NonSeasonalData_TestData,Winter_startyear_Data in zip(p["Model_object"],p["predictions"],p["location"]["latitude"],p["location"]["longitude"],p['seasonlist'],p['predictingyearlist'],p['Nonseasonal_TrainData'],p['TrainData'],p['TestData'],p['NonSeasonalData_TestData'],p['Winter_startyear_Data']):
				plt.figure(figsize=(25,20))	
				lat=np.unique(latitude)
				lon=np.unique(longitude)
				#plt.gca().xaxis.set_major_locator(mdates.DateFormatter('%Y'))
				plt.gca().xaxis.set_major_formatter(mdates.DateFormatter('%Y'))
				#plt.gca().xaxis.set_major_locator(mdates.MonthLocator(interval=12))  
				plt.gca().xaxis.set_minor_formatter(mdates.DateFormatter('%M'))
				plt.gca().xaxis.set_minor_locator(mdates.MonthLocator())
				plt.gcf().autofmt_xdate()
				plt.ylim([0,101])
				plt.yticks(np.arange(0,101,10))
				df1=pd.concat([Nonseasonal_TrainData,TrainData],ignore_index=True)
				df2=pd.concat([TestData,NonSeasonalData_TestData],ignore_index=True)
				AllData_Frame=pd.concat([df1,df2],ignore_index=True)
				AllData_Frame_Timeframe=AllData_Frame['timeframe']
				AllData_Frame_Timeframe=AllData_Frame_Timeframe.reshape(-1,1)
				AllData_Frame_Predictions=Model_Object.predict(AllData_Frame_Timeframe)
				AllData_Frame['Date_Format']=[dt.datetime.strptime(d,'%Y-%m').date() for d in AllData_Frame['Date_Format']]
				AllData_Frame_Sort=AllData_Frame.sort_values("Date_Format")
				AllData_Framexlim=np.asarray(AllData_Frame_Sort['Date_Format'])
				#TrainData['Date_Format']=[dt.datetime.strptime(d,'%Y-%m').date() for d in TrainData['Date_Format']]
				TrainData_Dateformat=[dt.datetime.strptime(d,'%Y-%m').date() for d in TrainData['Date_Format']]
				TrainData['Date_Format']=[dt.datetime.strptime(d,'%Y-%m').date() for d in TrainData['Date_Format']]
				TrainData_Frequency=TrainData[config['SPECIES']]
				Nonseasonal_TrainData['Date_Format']=[dt.datetime.strptime(d,'%Y-%m').date() for d in Nonseasonal_TrainData['Date_Format']]
				TestData_Dateformat=[dt.datetime.strptime(d,'%Y-%m').date() for d in TestData['Date_Format']]
				TestData_Frequency=TestData[config['SPECIES']]
				TestData['Date_Format']=[dt.datetime.strptime(d,'%Y-%m').date() for d in TestData['Date_Format']]
				NonSeasonalData_TestData['Date_Format']=[dt.datetime.strptime(d,'%Y-%m').date() for d in NonSeasonalData_TestData['Date_Format']]
				Winter_startyear_Data['Date_Format']=[dt.datetime.strptime(d,'%Y-%m').date() for d in Winter_startyear_Data['Date_Format']]
				plt.scatter([d+timedelta(15) for d in TrainData_Dateformat],TrainData_Frequency*100,label=SeasonTrainData_Label)
				TrainandTestData=pd.concat([TrainData,TestData],ignore_index=True)
				NonSeasonal_TrainandTestData=pd.concat([Nonseasonal_TrainData,NonSeasonalData_TestData],ignore_index=True)
				year_values=Nonseasonal_TrainData.YEAR.unique()
				for year in year_values:				             #Plotting dark blue line for every winter season belonging to train data
					if season=='Winter':
						seasondata_winter=TrainData[(TrainData['YEAR']==year)&(TrainData['MONTH']!=12)]
						seasondata_winter=seasondata_winter.append(TrainData[(TrainData['YEAR']==year-1)&(TrainData['MONTH']==12)],ignore_index=True)
						seasondata_winter_year=seasondata_winter[(seasondata_winter['YEAR']==year)]
						minvalue_maxyear_df=seasondata_winter_year[(seasondata_winter_year['MONTH']==seasondata_winter_year['MONTH'].max())]
						maxvalue_maxyear_df=Nonseasonal_TrainData[(Nonseasonal_TrainData['YEAR']==year)&(Nonseasonal_TrainData['MONTH']==seasondata_winter_year['MONTH'].max()+1)]
						maxvalue_maxyear_df['Date_Format']=[d-timedelta(15) for d in maxvalue_maxyear_df['Date_Format']]
						maxvalue_maxyear_df[config['SPECIES']]=float(float(minvalue_maxyear_df[config['SPECIES']])+float(maxvalue_maxyear_df[config['SPECIES']]))/2                #Last month of dark blue line of a winter season by considering mid point
						seasondata_winter_blue=seasondata_winter.append(maxvalue_maxyear_df)
						minvalue_minyear_df=Winter_startyear_Data[(Winter_startyear_Data['YEAR']==year-1)&(Winter_startyear_Data['MONTH']==11)]                  
						maxvalue_minyear_df=TrainData[(TrainData['YEAR']==year-1)&(TrainData['MONTH']==12)]
						minvalue_minyear_df[config['SPECIES']]=float(float(minvalue_minyear_df[config['SPECIES']]) + float(maxvalue_minyear_df[config['SPECIES']]))/2             #Starting month of dark blue line of a particular winter season by considering mid point
						minvalue_minyear_df['Date_Format']=[d+timedelta(15) for d in minvalue_minyear_df['Date_Format']]
						#seasondata_winter_blue=seasondata_winter_blue.append(Nonseasonal_TrainData[(Nonseasonal_TrainData['YEAR']==year-1)&(Nonseasonal_TrainData['MONTH']==11)])
						seasondata_winter_blue=seasondata_winter_blue.append(minvalue_minyear_df)
						seasondata_winter_blue=seasondata_winter_blue.sort(['YEAR','MONTH'], ascending=[True,True])
						seasondata_winter_blue['Date_Format']=[d+timedelta(15) for d in seasondata_winter_blue["Date_Format"]]
						season_array=np.asarray(seasondata_winter_blue[['Date_Format',config['SPECIES']]])
						for start, stop in zip(season_array[:-1], season_array[1:]):                                                 #Plotting dark blue line
							x, y = zip(start, stop)
							plt.plot(x,[v*100 for v in y],color='blue')
						area_startdate=np.asarray(seasondata_winter[(seasondata_winter['YEAR']==year-1)]['Date_Format'])
						area_enddate=np.asarray(Nonseasonal_TrainData[(Nonseasonal_TrainData['YEAR']==year)&(Nonseasonal_TrainData['MONTH']==seasondata_winter_year['MONTH'].max()+1)]['Date_Format'])
						plt.axvspan(area_startdate[0],area_enddate[0],color='b',alpha=0.1,lw=1)					         #Plotting vertical background bar for every winter season
					else:                                                                                                 #Plotting vertical background bar and dark blue line for seasons other than Winter
						seasondata_notwinter=TrainData[(TrainData['YEAR']==year)]
						minvalue_maxyear_df=seasondata_notwinter[(seasondata_notwinter['YEAR']==year)&(seasondata_notwinter['MONTH']==seasondata_notwinter['MONTH'].max())]
						maxvalue_maxyear_df=Nonseasonal_TrainData[(Nonseasonal_TrainData['YEAR']==year)&(Nonseasonal_TrainData['MONTH']==seasondata_notwinter['MONTH'].max()+1)]
						maxvalue_maxyear_df['Date_Format']=[d-timedelta(15) for d in maxvalue_maxyear_df['Date_Format']]
						maxvalue_maxyear_df[config['SPECIES']]=float(float(minvalue_maxyear_df[config['SPECIES']])+float(maxvalue_maxyear_df[config['SPECIES']]))/2
						seasondata_notwinter_blue=seasondata_notwinter.append(maxvalue_maxyear_df)
						minvalue_minyear_df=Nonseasonal_TrainData[(Nonseasonal_TrainData['YEAR']==year)&(Nonseasonal_TrainData['MONTH']==seasondata_notwinter['MONTH'].min()-1)]
						#minimum=minvalue_minyear_df[config['SPECIES']]
						maxvalue_minyear_df=seasondata_notwinter[(seasondata_notwinter['MONTH']==seasondata_notwinter['MONTH'].min())]
						minvalue_minyear_df[config['SPECIES']]=float(float(minvalue_minyear_df[config['SPECIES']]) + float(maxvalue_minyear_df[config['SPECIES']]))/2
						minvalue_minyear_df['Date_Format']=[d+timedelta(15) for d in minvalue_minyear_df['Date_Format']]
						#seasondata_notwinter_blue=pd.DataFrame({"Date_Format":seasondata_notwinter_blue['Date_Format'],config['SPECIES']:seasondata_notwinter_blue[config['SPECIES']]})
						seasondata_notwinter_blue=seasondata_notwinter_blue.append(minvalue_minyear_df)
						#seasondata_notwinter_blue=seasondata_notwinter_blue.append(Nonseasonal_TrainData[(Nonseasonal_TrainData['YEAR']==year)&(Nonseasonal_TrainData['MONTH']==seasondata_notwinter['MONTH'].min()-1)])
						seasondata_notwinter_blue['Date_Format']=[d+timedelta(15) for d in seasondata_notwinter_blue["Date_Format"]]
						seasondata_notwinter_blue=seasondata_notwinter_blue.sort(['YEAR','MONTH'],ascending=[True,True])
						season_array=np.asarray(seasondata_notwinter_blue[['Date_Format',config['SPECIES']]])
						for start, stop in zip(season_array[:-1], season_array[1:]):                                #Plotting dark blue line
							x, y = zip(start, stop)
							plt.plot(x,[v*100 for v in y],color='blue')
						area_startdate=np.asarray(seasondata_notwinter[(seasondata_notwinter['MONTH']==seasondata_notwinter['MONTH'].min())]['Date_Format'])
						area_enddate=np.asarray(Nonseasonal_TrainData[(Nonseasonal_TrainData['YEAR']==year)&(Nonseasonal_TrainData['MONTH']==seasondata_notwinter['MONTH'].max()+1)]['Date_Format'])			
						plt.axvspan(area_startdate[0],area_enddate[0],color='b',alpha=0.1,lw=1)                    #Plotting vertical bar
				
				def plot(Plot_type):
					#plt.text(0,1,config["SPECIES"].replace("_"," ")+"\n"+str(config['START_YEAR'])+"-"+str(config['END_YEAR'])+"\n"+str(season),horizontalalignment='left',fontsize=30)
					plt.title(config["SPECIES"].replace("_"," ")+"\n""\n"+str(config['START_YEAR'])+"-"+str(config['END_YEAR'])+"\n""\n"+str(season)+"\n",loc='left',fontsize=30)
					#plt.legend(fontsize ='x-small',labelspacing=0.2,bbox_to_anchor=(1, 1),bbox_transform=plt.gcf().transFigure)
					plt.tight_layout(pad=20)
					plt.xlabel("Time",fontsize=25,labelpad=20)
					plt.ylabel(YAxis_Label,fontsize=25,labelpad=20)
					plt.xticks(rotation='horizontal',ha="center")
					plt.gca().tick_params(axis='y', which='both', labelleft='on', labelright='on')                  #	places tick marks on both sides of Yaxis
					
					for tick in plt.gca().xaxis.get_major_ticks():
						tick.tick1line.set_markersize(0)
						tick.tick2line.set_markersize(0)
						tick.label1.set_horizontalalignment('center')	
					
					plt.setp(plt.gca().get_xminorticklabels(),visible=False)
					plt.setp(plt.gca().xaxis.get_ticklines(),markersize=15)
					plt.setp(plt.gca().yaxis.get_ticklines(),markersize=15)
					plt.setp(plt.gca().xaxis.get_ticklabels(),fontsize=20)
					plt.setp(plt.gca().yaxis.get_ticklabels(),fontsize=20)
					x1,x2,y1,y2=plt.axis()
					plt.xlim(AllData_Framexlim[0],AllData_Framexlim[-1])
					#plt.gca().spines['top'].set_visible(False)
					plt.gca().xaxis.set_ticks_position('bottom')
					insetfig= plt.axes([0.67,0.67,0.2,0.2])							#Setting coordinates and width,height of inset
					themap=Basemap(projection='merc',llcrnrlat=lat_min-config['GRID_SIZE'],urcrnrlat=lat_max+config['GRID_SIZE'],llcrnrlon=lon_min-config['GRID_SIZE'],urcrnrlon=lon_max+config['GRID_SIZE'],rsphere=6371200.,resolution='l',area_thresh=10000)
					reclats=[lat,lat+config['GRID_SIZE'],lat+config['GRID_SIZE'],lat]   #Rectangular latitude coordinates for displaying grid in plot
					reclons=[lon,lon,lon+config['GRID_SIZE'],lon+config['GRID_SIZE']]	#Rectangular longitude coordinates for displaying grid in plot
					#themap.bluemarble()
					themap.drawcoastlines()
					themap.drawcountries(linewidth=2)
					themap.drawstates()
					themap.drawmapboundary(fill_color='gainsboro')
					themap.fillcontinents(color='white')
					x3,y3=themap(reclons,reclats)
					x3y3=zip(x3,y3)
					p= Polygon(x3y3, facecolor='red', alpha=0.4)       #Plotting rectangular polygon grid in Basemap
					plt.gca().add_patch(p)    
					plt.title("Location",fontsize=25)
					figure_name=str(config['SPECIES'])+"-"+str(lat)+"-"+str(lon)+"-"+str(predicting_year)+"-"+str(season)+"-"+config['PREDICTOR']
					if not os.path.isdir(config["RUN_NAME"]):              #If there is no directory then create a new directory and save plots
						os.mkdir(config["RUN_NAME"])
					destination_dir=os.path.abspath(config["RUN_NAME"])
					plt.savefig(os.path.join(destination_dir,figure_name+Plot_type))        #Saving plot in specified directory   
					plt.xticks([])
					plt.yticks([])
					plt.close()
				if regline=='True':          #If regression line is True
					plt.plot([d+timedelta(15) for d in AllData_Frame_Sort["Date_Format"].tolist()],AllData_Frame_Sort[config['SPECIES']]*100,linewidth=0.6,alpha=0.7,label=NonSeasonalData_Label)
					plt.plot([d+timedelta(15) for d in AllData_Frame['Date_Format']],AllData_Frame_Predictions*100,'r-',linewidth=1.5,label=RegressorLine_Label)   #Plotting Regressor line for Test Data
					plt.scatter([d+timedelta(15) for d in TestData_Dateformat],TestData_Frequency*100,color='black',label=TestData_Label)
					max_month=TestData[(TestData['YEAR']==predicting_year)]
					minvalue_maxyear_df=TestData[(TestData['YEAR']==predicting_year)&(TestData['MONTH']==max_month['MONTH'].max())]
					maxvalue_maxyear_df=NonSeasonalData_TestData[(NonSeasonalData_TestData['YEAR']==predicting_year)&(NonSeasonalData_TestData['MONTH']==max_month['MONTH'].max()+1)]
					maxvalue_maxyear_df['Date_Format']=[d-timedelta(15) for d in maxvalue_maxyear_df['Date_Format']]
					maxvalue_maxyear_df[config['SPECIES']]=float(float(minvalue_maxyear_df[config['SPECIES']])+float(maxvalue_maxyear_df[config['SPECIES']]))/2
					TestData_blue=max_month.append(maxvalue_maxyear_df)
					TestData_blue=TestData_blue.append(TestData[(TestData['YEAR']==predicting_year-1)])
					if season=='Winter':                                        #Considering starting point and ending point for dark blue line for Test Data for winter season
						minvalue_minyear_df=Winter_startyear_Data[(Winter_startyear_Data['YEAR']==predicting_year-1)&(Winter_startyear_Data['MONTH']==11)]
						maxvalue_minyear_df=TestData[(TestData['YEAR']==predicting_year-1)&(TestData['MONTH']==12)]
					else:                                                       #Considering starting and ending points for dark blue line for Non Winter seasons
						minvalue_minyear_df=NonSeasonalData_TestData[(NonSeasonalData_TestData['YEAR']==predicting_year)&(NonSeasonalData_TestData['MONTH']==max_month['MONTH'].min()-1)]
						maxvalue_minyear_df=max_month[(max_month['MONTH']==max_month['MONTH'].min())]
					minvalue_minyear_df[config['SPECIES']]=float(float(minvalue_minyear_df[config['SPECIES']]) + float(maxvalue_minyear_df[config['SPECIES']]))/2	 #considering mid point for the starting point 
					minvalue_minyear_df['Date_Format']=[d+timedelta(15) for d in minvalue_minyear_df['Date_Format']]
					TestData_blue=TestData_blue.append(minvalue_minyear_df)	
					TestData_blue['Date_Format']=[d+timedelta(15) for d in TestData_blue["Date_Format"]]
					TestData_blue=TestData_blue.sort(['YEAR','MONTH'], ascending=[True,True])
					TestData_array=np.asarray(TestData_blue[['Date_Format',config['SPECIES']]])
					for start,stop in zip(TestData_array[:-1],TestData_array[1:]):                        #Plotting dark blue line only for test data
						x, y = zip(start,stop)
						plt.plot(x,[v*100 for v in y],color='blue')
					if season=='Winter':
						area_startdate=np.asarray(TestData[(TestData['YEAR']==predicting_year-1)]['Date_Format'])
					else:
						area_startdate=np.asarray(TestData[(TestData['MONTH']==TestData['MONTH'].min())]['Date_Format'])
					area_enddate=np.asarray(NonSeasonalData_TestData[(NonSeasonalData_TestData['YEAR']==predicting_year)&(NonSeasonalData_TestData['MONTH']==max_month['MONTH'].max()+1)]['Date_Format'])
					plt.axvspan(area_startdate[0],area_enddate[0],color='b',alpha=0.1,lw=1)                #Plotting vertical bar only for Test Data
					Plot_type="_withRegressionLine.png"
					if 'PLOT_SINGLE' not in config.keys():                 #Checking single plot mode                                
						plot(Plot_type)                                    
					else:                                                  #Plotting graph which belongs to a particular location(latitude,longitude),predicting year and season
						if config['PLOT_SINGLE']['LAT']==lat and config['PLOT_SINGLE']['LON']==lon and config['PLOT_SINGLE']['PREDICTING_YEAR']==predicting_year and config['PLOT_SINGLE']['SEASON']==season:
							plot(Plot_type)                                  #Plot single plot by considering values from config['PLOT_SINGLE']
				elif regline=='False':                  #Plotting everything from above if condition except regression line in line 443
					plt.plot([d+timedelta(15) for d in AllData_Frame_Sort["Date_Format"].tolist()],AllData_Frame_Sort[config['SPECIES']]*100,linewidth=0.6,alpha=0.7,label=NonSeasonalData_Label)
					plt.scatter([d+timedelta(15) for d in TestData_Dateformat],TestData_Frequency*100,color='black',label=TestData_Label)
					max_month=TestData[(TestData['YEAR']==predicting_year)]
					minvalue_maxyear_df=TestData[(TestData['YEAR']==predicting_year)&(TestData['MONTH']==max_month['MONTH'].max())]
					maxvalue_maxyear_df=NonSeasonalData_TestData[(NonSeasonalData_TestData['YEAR']==predicting_year)&(NonSeasonalData_TestData['MONTH']==max_month['MONTH'].max()+1)]
					maxvalue_maxyear_df['Date_Format']=[d-timedelta(15) for d in maxvalue_maxyear_df['Date_Format']]
					maxvalue_maxyear_df[config['SPECIES']]=float(float(minvalue_maxyear_df[config['SPECIES']])+float(maxvalue_maxyear_df[config['SPECIES']]))/2
					TestData_blue=max_month.append(maxvalue_maxyear_df)
					TestData_blue=TestData_blue.append(TestData[(TestData['YEAR']==predicting_year-1)])
					if season=='Winter':
						minvalue_minyear_df=Winter_startyear_Data[(Winter_startyear_Data['YEAR']==predicting_year-1)&(Winter_startyear_Data['MONTH']==11)]
						maxvalue_minyear_df=TestData[(TestData['YEAR']==predicting_year-1)&(TestData['MONTH']==12)]
					else:
						minvalue_minyear_df=NonSeasonalData_TestData[(NonSeasonalData_TestData['YEAR']==predicting_year)&(NonSeasonalData_TestData['MONTH']==max_month['MONTH'].min()-1)]
						maxvalue_minyear_df=max_month[(max_month['MONTH']==max_month['MONTH'].min())]
					minvalue_minyear_df[config['SPECIES']]=float(float(minvalue_minyear_df[config['SPECIES']]) + float(maxvalue_minyear_df[config['SPECIES']]))/2	
					minvalue_minyear_df['Date_Format']=[d+timedelta(15) for d in minvalue_minyear_df['Date_Format']]
					TestData_blue=TestData_blue.append(minvalue_minyear_df)	
					TestData_blue['Date_Format']=[d+timedelta(15) for d in TestData_blue["Date_Format"]]
					TestData_blue=TestData_blue.sort(['YEAR','MONTH'], ascending=[True,True])
					TestData_array=np.asarray(TestData_blue[['Date_Format',config['SPECIES']]])
					for start,stop in zip(TestData_array[:-1],TestData_array[1:]):
						x, y = zip(start,stop)
						plt.plot(x,[v*100 for v in y],color='blue')
					if season=='Winter':
						area_startdate=np.asarray(TestData[(TestData['YEAR']==predicting_year-1)]['Date_Format'])
					else:
						area_startdate=np.asarray(TestData[(TestData['MONTH']==TestData['MONTH'].min())]['Date_Format'])
					area_enddate=np.asarray(NonSeasonalData_TestData[(NonSeasonalData_TestData['YEAR']==predicting_year)&(NonSeasonalData_TestData['MONTH']==max_month['MONTH'].max()+1)]['Date_Format'])
					plt.axvspan(area_startdate[0],area_enddate[0],color='b',alpha=0.1,lw=1)
					Plot_type="_withoutRegressionLine.png"
					if 'PLOT_SINGLE' not in config.keys():
						plot(Plot_type)
					else:
						if config['PLOT_SINGLE']['LAT']==lat and config['PLOT_SINGLE']['LON']==lon and config['PLOT_SINGLE']['PREDICTING_YEAR']==predicting_year and config['PLOT_SINGLE']['SEASON']==season:
							plot(Plot_type)
				elif regline=="nodata":                   
					df1['Date_Format']=[dt.datetime.strptime(d,'%Y-%m').date() for d in df1['Date_Format']]
					AllTrainData_Frame_sort=df1.sort_values("Date_Format")
					plt.plot([d+timedelta(15) for d in AllTrainData_Frame_sort["Date_Format"].tolist()],AllTrainData_Frame_sort[config['SPECIES']]*100,linewidth=0.6,alpha=0.7,label=NonSeasonalData_Label)
					Plot_type="_withoutData.png"
					if 'PLOT_SINGLE' not in config.keys():
						plot(Plot_type)
					else:
						if config['PLOT_SINGLE']['LAT']==lat and config['PLOT_SINGLE']['LON']==lon and config['PLOT_SINGLE']['PREDICTING_YEAR']==predicting_year and config['PLOT_SINGLE']['SEASON']==season:
							plot(Plot_type)
				else:
					plt.close()
		
def plot_predictors(predictors,config, max_size,out_fname, minlimit = -100):
	predictor_coefs = []
	predictor_intercepts = []
	predictor_variance = []
	predictor_surprise = []
	predictor_train_maes = []
	predictor_test_maes = []
	predictor_names = []
	predictor_expvar = []
	for p in predictors:
		for model,score,errors,season,predicting_year,lat,long,expvar in zip(p["Model_object"],p["stats"]["score"],p["stats"]["mean_abs_errors"],p["seasonlist"],p["predictingyearlist"],p["location"]["latitude"],p["location"]["longitude"],p["stats"]["expvar"]):
			if predicting_year >= config['PREDICTION_START_YEAR']:
				predictor_coefs.append(model.coef_[0])
				predictor_intercepts.append(model.intercept_)
				predictor_expvar.append(expvar)
				predictor_variance.append(score[0])
				predictor_surprise.append(score[1])
				predictor_train_maes.append(errors[0])
				predictor_test_maes.append(errors[1])
				predictor_names.append(str(lat.values[0])+"_"+str(long.values[0])+"_"+str(predicting_year)+"_"+str(season))
	pred_df = pd.DataFrame({"name":predictor_names,"coef":predictor_coefs,"intercept":predictor_intercepts,"train_maes":predictor_train_maes,"test_maes":predictor_test_maes,"expvar":predictor_expvar,"test/train_mae":[tr/te for tr,te in zip(predictor_test_maes,predictor_train_maes)]}) #"r2_train":predictor_variance,"r2_test":predictor_surprise,
	pd.set_option('expand_frame_repr',False)
	print pred_df
	sorted_pred_df = pred_df.sort_values("test/train_mae")
	print sorted_pred_df
	plt.figure(figsize=(10,10))
	plt.scatter(predictor_train_maes,predictor_test_maes)
	plt.xlabel("Train MAE")
	plt.ylabel("Test MAE")
	#plt.show()
	plt.savefig(str(out_fname)+"predictor_plot_variance_by_surprise.png")
	plt.close()
