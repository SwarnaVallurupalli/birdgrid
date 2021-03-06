import numpy as np
from birdgridhelpers import load_observations,init_birdgrid,plot_observation_frequency,model_location_novelty_over_time,plot_birds_over_time, plot_predictors
import numpy as np
import glob
import math
import pickle
import os.path
import pandas as pd
from scipy import interpolate
import datetime as dt
from datetime import datetime
from mpl_toolkits.basemap import Basemap
from matplotlib.mlab import griddata
from scipy import interpolate
import csv 
import matplotlib.pyplot as plt
from sklearn import linear_model
import matplotlib.dates as mdates

species_list = ["Falco_sparverius","Melanerpes_carolinus","Lanius_ludovicianus","Cyanocitta_cristata","Carduelis_pinus"]
predictors = []
SEASONS = {"Winter": [12,1,2],"Spring": [3,4,5],"Summer":[6,7,8],"Fall":[9,10,11]}                   #Splitting months into 4 seasons

config={}                                                                                            #Creating a dictionary object
config["TIME_STEP"] = "monthly"                                                                      
config["ATTRIBUTES"] = ['LATITUDE','LONGITUDE','YEAR','MONTH']                                       #Considering the required attributes
config['START_YEAR']=2003                                                                            # Start_year will load the data from the specified year
config['PREDICTION_START_YEAR']=2010                                                                 #Prediction year will start from the specified year till 2012
config['END_YEAR']=2012                                                                               
config['GRID_SIZE']=3                                                                                  #Divides the map(latitude,longitude) into the specified grid size
config['PREDICTOR']="theilsen"                                                                    
config['use_chance_not_count']=True                                                                    #If set to true then chance mode , else Frequency mode
config['REGRESSION_LINE']=['True']#,'False','nodata']

''' Delete the # at the beginning of this line (and adjust the below) to enable single-plot mode, add a # to disable it again.
config['PLOT_SINGLE']={}
config['PLOT_SINGLE']['LAT']=46
config['PLOT_SINGLE']['LON']=-118
config['PLOT_SINGLE']['PREDICTING_YEAR']=2012
config['PLOT_SINGLE']['SEASON']="Winter"
#'''

for sp in species_list:                                                    #Iterating through every species
	config['SPECIES']=sp
	if config['use_chance_not_count']:
		Model_mode="chance_mode"
	else:
		Model_mode="count_mode"

	config["RUN_NAME"]=str(config['SPECIES'])+"-"+str(config['START_YEAR'])+"-"+str(config['END_YEAR'])+"-"+str(config['GRID_SIZE'])+"-"+str(config['PREDICTOR']+"-"+Model_mode)

	if os.path.isfile(config["RUN_NAME"]+"_predictors.p") and os.path.isfile(config["RUN_NAME"]+"_locations.p"):                   
		locations=pd.read_pickle(config["RUN_NAME"]+"_locations.p")
		with open(config["RUN_NAME"]+'_predictors.p',"rb") as pf:
			predictors = pickle.load(pf)
	else:
		if os.path.isfile(config["RUN_NAME"]+"_locations.p"):
			locations=pd.read_pickle(config["RUN_NAME"]+"_locations.p")
		else:
			observations = load_observations(config) #Load these in from somewhere, one row per observation, columns 0 and 1 are lat and lon
			locations=init_birdgrid(observations,config,SEASONS)  #Calculate these from the above, Array of dicts, each dict contains lat, lon and data for each timestep


		#Plot our species frequency observations
		plot_observation_frequency(locations,SEASONS,config)

		# matrix of models of shape locations x timesteps.

		for k,location in locations.groupby(['LATITUDE','LONGITUDE'],as_index=False):
			predictors.append(model_location_novelty_over_time(location,SEASONS,config))
		with open(config["RUN_NAME"]+'_predictors.p',"wb") as pf:
			pickle.dump(predictors,pf)

	plot_birds_over_time(predictors,locations,config)

	plot_predictors(predictors, config, max_size=100, out_fname =config['RUN_NAME'])