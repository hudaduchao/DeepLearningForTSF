# multichannel multi-step cnn
from math import sqrt
from numpy import split
from numpy import array
from pandas import read_csv
from sklearn.metrics import mean_squared_error
from matplotlib import pyplot
from keras.models import Sequential
from keras.layers import Dense
from keras.layers import Flatten
from keras.layers.convolutional import Conv1D
from keras.layers.convolutional import MaxPooling1D
"""
1.将单日数据(1113, 8)按周分割，成三维数据(159,7,8)分别表示（159周，步长7[一周七天]，每天8个特征），有点多此一举
2.将三维数据(159,7,8)展平成二维数据(1113, 8)，用于后续构建监督学习数据
3.将二维数据拼接成(14->7)，表示：前14天多变量->后7天单变量
"""
# 将数据按week分割成训练集和测试集
def split_dataset(data):
	# 分割成训练集和测试集
	train, test = data[1:-328], data[-328:-6]
	# 分割成以周为单位
	train = array(split(train, len(train)/7))
	test = array(split(test, len(test)/7))
	return train, test

# 评估真实值和预测值的RMSE
def evaluate_forecasts(actual, predicted):
	scores = list()
	# 评估预测出来的每个输出，每个输出有7列（步长为7），计算每一列（步）的RMSE
	for i in range(actual.shape[1]):
		mse = mean_squared_error(actual[:, i], predicted[:, i])
		rmse = sqrt(mse)
		scores.append(rmse)
	# 计算整体行列的RMSE
	s = 0
	for row in range(actual.shape[0]):
		for col in range(actual.shape[1]):
			s += (actual[row, col] - predicted[row, col])**2
	score = sqrt(s / (actual.shape[0] * actual.shape[1]))
	return score, scores

# 统计得分
def summarize_scores(name, score, scores):
	s_scores = ', '.join(['%.1f' % s for s in scores])
	print('%s: [%.3f] %s' % (name, score, s_scores))

# 构造“多对多(14->7)”的监督学习型数据
def to_supervised(train, input_step, out_step=7):
	# 将3维数据(159,7,8)展平成2维(1113,8)
	data = train.reshape((train.shape[0]*train.shape[1], train.shape[2]))
	X, y = list(), list()
	in_start = 0
	# 遍历数据，构建“多对多(14->7)”的监督学习型数据
	for _ in range(len(data)):
		#定义每次 输入 截取数据的结尾位置
		in_end = in_start + input_step
		#定义每次 输出 截取数据的结尾位置
		out_end = in_end + out_step
		
		if out_end <= len(data):
			# 输入X索引：eg:(0~14)、(1~15)、(2~16)、(3~17)
			X.append(data[in_start:in_end, :])
			# 输出Y索引：eg:(14~21)、(15~22)、(16~23)、(17~24)
			y.append(data[in_end:out_end, 0])
		# 取数的起始位置向后位移1
		in_start += 1
	# 输入(1093,14,8) 输出(1093,7)
	return array(X), array(y)

# 构建和训练模型
def build_model(train, input_step):
	# 构造“多对多(14->7)”的监督学习型数据
	# train_x(1093,14,8),train_y(1093,7)
	train_x, train_y = to_supervised(train, input_step)
	# 训练次数70，批次大小16，输入时间步为14，特征值为8，每次预测7条数据
	verbose, epochs, batch_size = 0, 70, 16
	n_timesteps, n_features, n_outputs = train_x.shape[1], train_x.shape[2], train_y.shape[1]
	# define model
	model = Sequential()
	model.add(Conv1D(filters=32, kernel_size=3, activation='relu', input_shape=(n_timesteps,n_features)))
	model.add(Conv1D(filters=32, kernel_size=3, activation='relu'))
	model.add(MaxPooling1D(pool_size=2))
	model.add(Conv1D(filters=16, kernel_size=3, activation='relu'))
	model.add(MaxPooling1D(pool_size=2))
	model.add(Flatten())
	model.add(Dense(100, activation='relu'))
	model.add(Dense(n_outputs))
	model.compile(loss='mse', optimizer='adam')
	# fit network
	model.fit(train_x, train_y, epochs=epochs, batch_size=batch_size, verbose=verbose)
	return model

# make a forecast
def forecast(model, history, input_step):
	# 将3维数据(159,7,8)展平成2维(1113,8)
	data = array(history)
	data = data.reshape((data.shape[0]*data.shape[1], data.shape[2]))
	# 每次取历史数据的最后14条，作为输入,input_x(14,8)
	input_x = data[-input_step:, :]
	# 重构输入形状(14,8)->(1,14,8)
	input_x = input_x.reshape((1, input_x.shape[0], input_x.shape[1]))
	# 预测未来一周值(1,7)，并返回需要的格式(7,)
	yhat = model.predict(input_x, verbose=0)
	yhat = yhat[0]
	return yhat

# 拟合、预测、评估模型
def evaluate_model(train, test, input_step):
	# fit model
	model = build_model(train, input_step)
	# 获取array类型的训练集数据history = [array([[]])]->(159,7,8)
	history = [x for x in train]
	# walk-forward validation over each week
	predictions = list()
	# 预测测试集中对应的每条数据
	for i in range(len(test)):
		# 按周(每次预测7条)进行预测，并保存预测结果，完成本次预测后追加一条真实值用于下次预测
		yhat_sequence = forecast(model, history, input_step)
		predictions.append(yhat_sequence)
		history.append(test[i, :])
	# 预测完成后，评估结果
	predictions = array(predictions)
	score, scores = evaluate_forecasts(test[:, :, 0], predictions)
	return score, scores


dataset = read_csv('household_power_consumption_days.csv', header=0, infer_datetime_format=True, parse_dates=['datetime'], index_col=['datetime'])
# 将数据按week分割成训练集(159,7,8)和测试集(46,7,8)
train, test = split_dataset(dataset.values)
# evaluate model and get scores
input_step = 14
score, scores = evaluate_model(train, test, input_step)
# 统计得分
summarize_scores('cnn', score, scores)
# 画出得分图
days = ['sun', 'mon', 'tue', 'wed', 'thr', 'fri', 'sat']
pyplot.plot(days, scores, marker='o', label='cnn')
pyplot.show()